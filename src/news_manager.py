# -*- coding: utf-8 -*-
"""
Module Name: news_manager.py

Description:
The NewsManager module fetches stock-related headlines from various RSS feeds,
provides trade recommendations based on the headlines using ChatGPT,
and stores the recommendations in a MySQL database.

Author: elreysausage
Date: 2024-11-15
"""

import os
from datetime import datetime, time, timedelta
import logging
from logging.handlers import TimedRotatingFileHandler
import sys
import time as tm
from typing import Callable

import feedparser
import openai
import mysql.connector


class PrintToLogger(object):
    """
    A class to redirect print statements to a logger.
    """
    def __init__(self, level: Callable[[str], None]):
        """
        Initializes the PrintToLogger class with a logging level.

        Parameters:
            level: The logging level to use.
        """
        self.level = level

    def write(self, message: str) -> None:
        """
        Writes the message to the logger.

        Parameters:
            message: The message to log.
        """
        if message.strip():
            self.level(message)

    def flush(self) -> None:
        """
        Flushes the logger.
        """
        pass


class NewsManager(object):
    """
    A class for fetching news headlines and providing trade recommendations.

    Attributes:
        MARKET_OPEN_TIME: The time when the market opens.
        MARKET_CLOSE_TIME: The time when the market closes.
        RSS_FEEDS: A dictionary of RSS feeds for fetching news headlines.
    """
    MARKET_OPEN_TIME = time(9, 00)
    MARKET_CLOSE_TIME = time(21, 00)
    RSS_FEEDS = {
        "Reuters": "http://feeds.reuters.com/reuters/businessNews",
        "Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
        "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "Investing.com": "https://www.investing.com/rss/news.rss",
        "Financial Times": "https://www.ft.com/?format=rss",
        "The Wall Street Journal": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "CNBC Business News": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    }

    def __init__(self, lookback_minutes: int, sleep_interval: int, run_during_market_hours: bool):
        """
        Initializes the NewsManager class with default settings.

        Parameters:
            lookback_minutes: Number of minutes to look back for news headlines.
            sleep_interval: Number of seconds to sleep between fetching headlines.
            run_during_market_hours: Flag to run the manager only during market hours.

        Environment Variables:
            DB_HOST: The hostname or IP address of the database server.
            DB_USER: The username for database authentication.
            DB_PASSWORD: The password for the specified database user.
            DB_NAME: The name of the database to connect to.
            OPENAI_API_KEY: The API key for authenticating with OpenAI.
        """
        self.setup_logger()
        self.redirect_print_to_logger()
        self.check_env_vars(["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "OPENAI_API_KEY"])
        self.connect_db()
        self.create_tables()
        self.lookback_minutes = lookback_minutes
        self.sleep_interval = sleep_interval
        self.run_during_market_hours = run_during_market_hours
        openai.api_key = os.environ.get("OPENAI_API_KEY")

    def setup_logger(self) -> None:
        """
        Sets up a logger for the NewsManager class.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "log")
        self.logger = logging.getLogger("NewsManager")
        self.logger.setLevel(logging.DEBUG)
        file_handler = TimedRotatingFileHandler(
            log_file, when="midnight", interval=1, backupCount=7
        )
        file_handler.suffix = "%Y-%m-%d"
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(file_handler)

    def redirect_print_to_logger(self) -> None:
        """
        Redirects print statements to the logger.
        """
        sys.stdout = PrintToLogger(self.logger.info)
        sys.stderr = PrintToLogger(self.logger.error)

    def connect_db(self) -> None:
        """
        Connects to the MySQL database.
        """
        self.conn = mysql.connector.connect(
            host=os.environ.get('DB_HOST'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            database=os.environ.get('DB_NAME')
        )
        self.cursor = self.conn.cursor(dictionary=True)

    @staticmethod
    def check_env_vars(required_vars: list) -> None:
        """
        Checks if all required environment variables are set.

        Parameters:
            required_vars: A list of required environment variables.

        Raises:
            EnvironmentError: If any required environment variables are missing.
        """
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            raise EnvironmentError(
                f"Missing environment variables: {', '.join(missing_vars)}. "
                "Please set them before running this function."
            )
    
    def close_db(self) -> None:
        """
        Closes the cursor and connection to the MySQL database.
        """
        self.cursor.close()
        self.conn.close()

    def create_tables(self) -> None:
        """
        Creates the necessary tables in the database if they do not already exist.
        """
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_signals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                source VARCHAR(255),
                headline TEXT,
                action VARCHAR(10),
                symbol VARCHAR(10),
                rationale TEXT,
                headline_timestamp DATETIME,
                record_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                price_at_record FLOAT,
                price_plus_30min FLOAT,
                price_plus_1hr FLOAT,
                price_plus_3hr FLOAT,
                price_eod FLOAT,
                UNIQUE (headline(255))
            )
        ''')
        self.conn.commit()

    @staticmethod
    def print_separator() -> None:
        """
        Prints a separator line.
        """
        print(50 * "-")

    @property
    def is_market_open(self) -> bool:
        """
        Check if the market is open based on time and weekday.
        
        Returns:
            True if the market is open, False otherwise.
        """
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        return self.MARKET_OPEN_TIME <= now.time() <= self.MARKET_CLOSE_TIME

    def get_news_headlines(self) -> list:
        """
        Fetches stock-related headlines from a list of RSS feeds.

        Returns:
            recent_headlines: Recent headlines with source, title, and published time.
        """
        recent_headlines = []
        time_threshold = datetime.now() - timedelta(minutes=self.lookback_minutes)

        for source, url in self.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed["entries"]:
                    published_time = datetime.now()
                    if 'published' in entry:
                        published_time = datetime(*entry["published_parsed"][:6])
                    if published_time >= time_threshold:
                        headline = {
                            "source": source,
                            "title": entry["title"],
                            "published": published_time.isoformat()
                        }
                        recent_headlines.append(headline)
            except Exception as e:
                print(f"Failed to fetch from {source}. Error: {e}")
        return recent_headlines

    def get_trade_recommendation(self, headline: str) -> dict:
        """
        Uses ChatGPT to provide trade recommendations based on a news headline.

        Parameters:
            headline: The headline to interpret.

        Returns:
            recommendation: Trade recommendation with action, ticker, and rationale.
        """
        prompt = (
            "Given the following news headline, recommend an intraday trade action if it "
            "could cause an immediate and substantial market response specifically for a "
            "publicly traded stock (equity) on major exchanges. Only provide a trade recommendation "
            "if the news is likely to result in a strong, high-conviction intraday price movement "
            "within the same trading day.\n\n"
            
            "If the news is unlikely to cause a significant impact on intraday prices or "
            "if it does not pertain to an individual stock, respond with 'No trade recommendation.' "
            "Format the response as follows:\n\n"
            
            "Action: Buy/Sell (or 'No trade recommendation')\n"
            "Ticker: Only the ticker symbol itself (e.g., 'AAPL' for Apple Inc.), with no additional text\n"
            "Rationale: Brief reasoning with emphasis on the strength of the expected impact\n\n"
            
            f"Headline: {headline}"
        )
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response['choices'][0]['message']['content']
            recommendation = self.parse_recommendation(content)
        except Exception as e:
            print(f"Failed to get trade recommendation for headline: {headline}. Error: {e}")
            recommendation = None
        return recommendation

    @staticmethod
    def parse_recommendation(content: str) -> dict:
        """
        Parses the structured response content into a dictionary format.

        Parameters:
            content: The content response from ChatGPT.

        Returns:
            recommendation: Trade recommendation with action, ticker, and rationale.
        """
        lines = content.split("\n")
        recommendation = {}
        for line in lines:
            if "Action:" in line:
                action = line.split(": ")[1].strip()
                if action.lower() == "no trade recommendation":
                    return None
                recommendation["action"] = action
            elif "Ticker:" in line:
                recommendation["ticker"] = line.split(": ")[1].strip()
            elif "Rationale:" in line:
                recommendation["rationale"] = line.split(": ")[1].strip()
        return recommendation if recommendation else None
    
    def ensure_connection(self) -> None:
        """
        Ensures that the database connection is active.
        """
        try:
            self.conn.ping(reconnect=True, attempts=3, delay=2)
        except mysql.connector.Error:
            self.connect_db()

    def commit_news_signals(self, headline: dict, recommendation: dict):
        """
        Commits the news headline and trade recommendation to the database.

        Parameters:
            headline: The news headline to commit.
            recommendation: The corresponding trade recommendation.
        """
        self.ensure_connection()
        insert_query = (
            "INSERT IGNORE INTO news_signals (source, headline, action, symbol, "
            "rationale, headline_timestamp) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        data = (
            headline["source"],
            headline["title"],
            recommendation.get("action"),
            recommendation.get("ticker"),
            recommendation.get("rationale"),
            headline["published"]
        )
        try:
            self.cursor.execute(insert_query, data)
            self.conn.commit()
        except mysql.connector.Error as e:
            print(f"Database error occurred: {e}")
            raise RuntimeError(f"Failed to execute query: {insert_query} with data: {data}") from e

    def start(self) -> None:
        """
        Initiates the running loop to fetch news headlines and provide trade recommendations.
        """
        while True:
            if not self.run_during_market_hours or self.is_market_open:
                headlines = self.get_news_headlines()
                self.print_separator()
                print("Recent Stock Headlines (Last 30 Minutes):")
                self.print_separator()
                for headline in headlines:
                    print(f"{headline['published']} - {headline['source']}: {headline['title']}")
                    recommendation = self.get_trade_recommendation(headline['title'])
                    if recommendation:
                        print("\nTrade Recommendation:")
                        print(f"Action: {recommendation.get('action', 'N/A')}")
                        print(f"Ticker: {recommendation.get('ticker', 'N/A')}")
                        print(f"Rationale: {recommendation.get('rationale', 'N/A')}")
                        self.commit_news_signals(headline, recommendation)
                    else:
                        print("No high-conviction trade recommendation.")
                    self.print_separator()
                print(f"\nSleeping for {self.sleep_interval} seconds...\n")
            else:
                print("Market is closed. Sleeping until next market open...")
                next_open = datetime.combine(datetime.now().date(), self.MARKET_OPEN_TIME)
                if datetime.now().time() > self.MARKET_CLOSE_TIME:
                    next_open += timedelta(days=1)
                sleep_time = (next_open - datetime.now()).seconds
                tm.sleep(sleep_time)
            tm.sleep(self.sleep_interval)


if __name__ == "__main__":
    news_manager = NewsManager(
        lookback_minutes=30,
        sleep_interval=60,
        run_during_market_hours=True
    )
    news_manager.start()
