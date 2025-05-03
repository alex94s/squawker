# -*- coding: utf-8 -*-
"""
Module Name: price_fetcher.py

Description:
The PriceFetcher module fetches stock prices for trade recommendations
and updates the database with the prices. It is used by the NewsManager
module to provide price data for the trade recommendations.

Author: elreysausage
Date: 2024-11-15
"""

from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore', module='yfinance')

import pandas as pd
import pytz
import yfinance as yf

from src.news_manager import NewsManager


class PriceFetcher(NewsManager):
    """
    A class for retrieving stock prices and updating the database with the prices
    for trade recommendations.

    Attributes:
        timezone: The timezone for the stock prices.
    """
    TIMEZONE = pytz.timezone("Europe/London")

    def __init__(self):
        """
        Initializes the PriceFetcher object.
        """
        self.connect_db()

    def get_recommendations(self) -> list:
        """
        Retrieve all recommendations from the database.
        
        Returns:
            A list of dictionaries containing symbol and record_timestamp
            for each recommendation.
        """
        self.cursor.execute("SELECT symbol, record_timestamp FROM news_signals")
        recommendations = self.cursor.fetchall()
        return recommendations

    def download_price_data(
        self, 
        symbols: list, 
        date: datetime, 
        interval: str
    ) -> pd.DataFrame:
        """
        Downloads prices for multiple symbols for the specified date.

        Parameters:
            symbols: A list of symbols to download data for.
            date: The date to download data for.
            interval: The interval for data ('1m' for intraday, '1d' for end-of-day).
        
        Returns:
            A DataFrame containing historical price data.
        """
        try:
            data = yf.download(
                tickers=symbols,
                interval=interval,
                start=date.strftime('%Y-%m-%d'),
                end=(date + timedelta(days=1)).strftime('%Y-%m-%d'),
                progress=False,
                group_by="ticker"
            )
            if interval in ["1m", "2m", "5m", "15m", "30m", "60m", "90m"]:
                data.index = data.index.tz_convert(self.TIMEZONE)
            return data
        except Exception as e:
            print(f"Error downloading data: {e}")
            return None

    def update_price_for_intervals(
            self, 
            intraday_data: pd.DataFrame, 
            eod_data: pd.DataFrame, 
            symbol: str, 
            record_timestamp: datetime
        ) -> None:
        """
        Update the price in the database for each specified time interval
        relative to the record_timestamp.

        Parameters:
            intraday_data: The intraday price data.
            eod_data: The end-of-day price data.
            symbol: The symbol to update the price for.
            record_timestamp: The timestamp of the news record.
        """
        record_timestamp = record_timestamp.astimezone(self.TIMEZONE)
        timestamps = {
            "price_at_record": record_timestamp,
            "price_plus_30min": record_timestamp + timedelta(minutes=30),
            "price_plus_1hr": record_timestamp + timedelta(hours=1),
            "price_plus_3hr": record_timestamp + timedelta(hours=3),
        }
        current_time = datetime.now(self.TIMEZONE)
        price_data = {}

        for label, timestamp in timestamps.items():
            try:
                if timestamp > current_time:
                    price_data[label] = None
                    continue
                symbol_data = intraday_data[symbol]['Close']
                nearest_time = symbol_data.index.asof(timestamp)
                if nearest_time is not None and nearest_time <= current_time:
                    price_data[label] = symbol_data.get(nearest_time, None)
                else:
                    price_data[label] = None
            except:
                price_data[label] = None
                
        try:
            eod_price = eod_data[symbol]['Close'].iloc[0] if symbol in eod_data else None
            price_data["price_eod"] = eod_price
        except Exception as e:
            price_data["price_eod"] = None

        for key in price_data:
            if pd.isna(price_data[key]):
                price_data[key] = None

        update_query = (
            "UPDATE news_signals SET "
            "price_at_record = %s, price_plus_30min = %s, price_plus_1hr = %s, "
            "price_plus_3hr = %s, price_eod = %s "
            "WHERE symbol = %s AND record_timestamp = %s"
        )
        self.cursor.execute(update_query, (
            price_data["price_at_record"],
            price_data["price_plus_30min"],
            price_data["price_plus_1hr"],
            price_data["price_plus_3hr"],
            price_data["price_eod"],
            symbol,
            record_timestamp
        ))
        self.conn.commit()

    def process_recommendations(self) -> None:
        """
        Process all recommendations in the database, updating the price
        for each time interval relative to the record timestamp.
        """
        recommendations = self.get_recommendations()
        recommendations_by_date = {}

        for recommendation in recommendations:
            symbol = recommendation['symbol']
            record_timestamp = recommendation['record_timestamp']
            date = record_timestamp.date()
            if date not in recommendations_by_date:
                recommendations_by_date[date] = []
            recommendations_by_date[date].append((symbol, record_timestamp))

        for date, recs in recommendations_by_date.items():
            symbols = list(set([rec[0] for rec in recs]))
            intraday_data = self.download_price_data(symbols, date, '1m')
            eod_data = self.download_price_data(symbols, date, '1d')
    
            if intraday_data is not None and eod_data is not None:
                for symbol, record_timestamp in recs:
                    try:
                        self.update_price_for_intervals(
                            intraday_data, 
                            eod_data, symbol, 
                            record_timestamp
                        )
                    except Exception as e:
                        print(f"Error for {symbol} at {record_timestamp}: {e}")
        self.close_db()


if __name__ == "__main__":
    price_fetcher = PriceFetcher()
    price_fetcher.process_recommendations()
