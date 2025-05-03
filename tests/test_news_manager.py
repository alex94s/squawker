# -*- coding: utf-8 -*-
"""
Module: test_news_manager.py

Description:
This module contains the unit tests for the NewsManager module. The unit tests in this 
module ensure the correctness and reliability of the functions utilised by using
mock objects to simulate database interactions and other dependencies.

Author: Alex Schneider
Date: 2025-02-03
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.news_manager import NewsManager, PrintToLogger


class TestNewsManager(unittest.TestCase):
    """
    A class for testing the NewsManager module.
    """
    @patch('src.news_manager.os.environ.get')
    @patch('src.news_manager.mysql.connector.connect')
    def setUp(self, mock_connect: MagicMock, mock_get: MagicMock) -> None:
        """
        Set up the test case.

        Args:
            mock_connect: A mock object for the MySQL connection.
            mock_get: A mock object for the os.environ.get function.
        """
        mock_get.side_effect = lambda key: {
            'DB_HOST': 'localhost',
            'DB_USER': 'user',
            'DB_PASSWORD': 'password',
            'DB_NAME': 'news_db',
            'OPENAI_API_KEY': 'test_api_key'
        }.get(key)

        self.news_manager = NewsManager(
            lookback_minutes=30, 
            sleep_interval=60, 
            run_during_market_hours=False
        )
        self.news_manager.lookback_minutes = 60
        self.news_manager.RSS_FEEDS = {
            "TestSource": "http://example.com/rss"
        }

    def test_setup_logger(self) -> None:
        """
        Test the setup_logger method.
        """
        self.assertIsNotNone(self.news_manager.logger)
        self.assertEqual(self.news_manager.logger.name, "NewsManager")

    def test_redirect_print_to_logger(self) -> None:
        """
        Test the redirect_print_to_logger method.
        """
        self.assertIsInstance(sys.stdout, PrintToLogger)
        self.assertIsInstance(sys.stderr, PrintToLogger)

    @patch("feedparser.parse")
    def test_get_news_headlines(self, mock_feedparser: MagicMock) -> None:
        """
        Test the get_news_headlines method.

        Args:
            mock_feedparser: A mock object for the feedparser.parse function.
        """
        recent_time = datetime.now() - timedelta(minutes=30)
        old_time = datetime.now() - timedelta(minutes=90)
        mock_feed = MagicMock()
        mock_feed = {
            "entries": [
                {
                    "title": "Stock Market Hits New High",
                    "published": recent_time.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    "published_parsed": recent_time.timetuple(),
                },
                {
                    "title": "Tech Stocks Rally",
                    "published": old_time.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    "published_parsed": old_time.timetuple(),
                },
            ]
        }
        mock_feedparser.return_value = mock_feed
        headlines = self.news_manager.get_news_headlines()
        self.assertEqual(len(headlines), 1)
        self.assertEqual(headlines[0]["source"], "TestSource")
        self.assertEqual(headlines[0]["title"], "Stock Market Hits New High")

    @patch('src.news_manager.openai.ChatCompletion.create')
    def test_get_trade_recommendation(self, mock_create: MagicMock) -> None:
        """
        Test the get_trade_recommendation method.
        
        Args:
            mock_create: A mock object for the openai.ChatCompletion.create function.
        """
        mock_create.return_value = {
            'choices': [{
                'message': {
                    'content': 'Action: Buy\nTicker: AAPL\nRationale: Strong earnings report'
                }
            }]
        }
        recommendation = self.news_manager.get_trade_recommendation(
            'Apple reports strong earnings'
        )
        self.assertEqual(recommendation['action'], 'Buy')
        self.assertEqual(recommendation['ticker'], 'AAPL')
        self.assertEqual(recommendation['rationale'], 'Strong earnings report')

    @patch('src.news_manager.mysql.connector.connect')
    def test_connect_db(self, mock_connect: MagicMock) -> None:
        """
        Test the connect_db method.

        Args:
            mock_connect: A mock object for the MySQL connection.
        """
        self.news_manager.connect_db()
        self.assertIsNotNone(self.news_manager.conn)
        self.assertIsNotNone(self.news_manager.cursor)

    def test_check_env_vars(self) -> None:
        """
        Test the check_env_vars method.
        """
        with self.assertRaises(EnvironmentError):
            NewsManager.check_env_vars(['MISSING_VAR'])

    @patch('src.news_manager.mysql.connector.connect')
    def test_create_tables(self, mock_connect: MagicMock) -> None:
        """
        Test the create_tables method.

        Args:
            mock_connect: A mock object for the MySQL connection.
        """
        self.news_manager.create_tables()
        self.news_manager.cursor.execute.assert_called()

    @patch('src.news_manager.mysql.connector.connect')
    def test_commit_news_signals(self, mock_connect: MagicMock) -> None:
        """
        Test the commit_news_signals method.

        Args:
            mock_connect: A mock object for the MySQL connection.
        """
        headline = {
            "source": "Test Source",
            "title": "Test Headline",
            "published": datetime.now().isoformat()
        }
        recommendation = {
            "action": "Buy",
            "ticker": "AAPL",
            "rationale": "Strong earnings report"
        }
        self.news_manager.commit_news_signals(headline, recommendation)
        self.news_manager.cursor.execute.assert_called()

    def test_is_market_open(self) -> None:
        """
        Test the is_market_open property.
        """
        self.news_manager.MARKET_OPEN_TIME = datetime.now().time()
        self.news_manager.MARKET_CLOSE_TIME = (datetime.now() + timedelta(hours=1)).time()
        self.assertTrue(self.news_manager.is_market_open)


if __name__ == '__main__':
    unittest.main()