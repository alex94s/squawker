# -*- coding: utf-8 -*-
"""
Module: test_price_fetcher.py

Description:
This module contains the unit tests for the PriceFetcher module. The unit tests in this 
module ensure the correctness and reliability of the functions utilised by using
mock objects to simulate database interactions and other dependencies.

Author: Alex Schneider
Date: 2025-02-03
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

import pandas as pd
import pytz

from src.price_fetcher import PriceFetcher


class TestPriceFetcher(unittest.TestCase):
    """
    A class for testing the PriceFetcher module.
    """
    def setUp(self):
        """
        Set up the test case.
        """
        self.fetcher = PriceFetcher()
        self.fetcher.cursor = MagicMock()
        self.fetcher.conn = MagicMock()
        self.fetcher.TIMEZONE = pytz.timezone("Europe/London")
    
    @patch("src.price_fetcher.yf.download")
    def test_download_price_data(self, mock_yfinance: MagicMock) -> None:
        """
        Test downloading price data.

        Args:
            mock_yfinance: A mock object for the yfinance.download function.
        """
        date = datetime(2024, 2, 1)
        symbols = ["AAPL", "GOOGL"]
        interval = "1m"

        mock_data = pd.DataFrame({
            ("AAPL", "Close"): [150.0, 151.0],
            ("GOOGL", "Close"): [2800.0, 2810.0]
        }, index=pd.to_datetime(["2024-02-01 09:30:00", "2024-02-01 09:31:00"]))

        mock_data.index = mock_data.index.tz_localize("UTC")
        mock_yfinance.return_value = mock_data
        data = self.fetcher.download_price_data(symbols, date, interval)
        self.assertIsInstance(data, pd.DataFrame)
        self.assertTrue("AAPL" in data.columns.get_level_values(0))
        self.assertTrue("GOOGL" in data.columns.get_level_values(0))
    
    def test_get_recommendations(self) -> None:
        """
        Test getting recommendations from the database.
        """
        self.fetcher.cursor.fetchall.return_value = [
            {"symbol": "AAPL", "record_timestamp": datetime(2024, 2, 1, 14, 30)},
            {"symbol": "GOOGL", "record_timestamp": datetime(2024, 2, 1, 15, 45)}
        ]
        recommendations = self.fetcher.get_recommendations()
        self.assertEqual(len(recommendations), 2)
        self.assertEqual(recommendations[0]["symbol"], "AAPL")
    
    @patch("src.price_fetcher.PriceFetcher.download_price_data")
    def test_process_recommendations(self, mock_download: MagicMock) -> None:
        """
        Test processing recommendations.

        Args:
            mock_download: A mock object for the download_price_data function.
        """
        self.fetcher.get_recommendations = MagicMock(return_value=[
            {"symbol": "AAPL", "record_timestamp": datetime(2024, 2, 1, 14, 30)},
            {"symbol": "GOOGL", "record_timestamp": datetime(2024, 2, 1, 15, 45)}
        ])
        mock_price_data = pd.DataFrame({
            ("AAPL", "Close"): [150.0, 151.0],
            ("GOOGL", "Close"): [2800.0, 2810.0]
        }, index=pd.to_datetime(["2024-02-01 09:30:00", "2024-02-01 09:31:00"]))

        mock_price_data.index = mock_price_data.index.tz_localize("UTC")
        mock_download.return_value = mock_price_data
        self.fetcher.update_price_for_intervals = MagicMock()
        self.fetcher.process_recommendations()
        self.fetcher.update_price_for_intervals.assert_called()
        
    def tearDown(self) -> None:
        """
        Tear down the test case.
        """
        self.fetcher.close_db()


if __name__ == "__main__":
    unittest.main()
