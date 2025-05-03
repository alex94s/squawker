# squawker

## Table of Contents
1. [Description](#description)
2. [Requirements](#requirements)
3. [Modules](#modules)
4. [Testing](#testing)
5. [Version and Updates](#version-and-updates)
6. [Disclaimer](#disclaimer)

## Description
**squawker** is an automated stock news analysis and trading recommendation tool that fetches real-time headlines from various financial news sources, interprets them using OpenAI's ChatGPT, and generates high-conviction intraday trade recommendations. These recommendations are stored in a MySQL database for further analysis and can be used as part of an automated trading strategy.

## Requirements
The following requirements must be met prior to running the ithaka modules:

1. **Python Environment**:
   - Ensure all dependent packages are installed (`requirements.txt`).
2. **Database**:
   - A MySQL database with set environment variables for database credentials.
3. **OpenAI Account**:
   - A funded OpenAI account with set environment variable for API key.

### Environment Variables Setup
Running the following commands in the terminal **within the project environment** will create the necessary environment variables:

  ```bash
  export DB_HOST='your_host'
  export DB_USER='your_user'
  export DB_PASSWORD='your_password'
  export DB_NAME='your_database'
  export OPENAI_API_KEY='your_api_key'
  ```

## Modules

### NewsManager
- **File**: `news_manager.py`
- **Purpose**: The NewsManager module collects real-time financial news headlines from various RSS feeds and generates trade recommendations based on sentiment analysis using OpenAI's ChatGPT.
- **Features**:
  - **News Collection**: Aggregates news headlines from multiple financial sources (e.g., Reuters, Bloomberg, MarketWatch).
  - **Trade Recommendations**: Uses AI to interpret headlines and provide high-confidence intraday buy/sell recommendations.
  - **Database Integration**: Saves each headline and recommendation to a MySQL database, including details like source, headline, action, and rationale.

### PriceFetcher
- **File**: `price_fetcher.py`
- **Purpose**: The PriceFetcher module retrieves precise intraday price data for specific timestamps and stores it in a MySQL database to track performance at various intervals relative to the headline's release.
- **Features**:
  - **Batch Price Retrieval**: Downloads minute-level price data for stocks in bulk using `yfinance`.
  - **Timestamped Price Tracking**: Tracks stock prices at specific intervals, such as the exact time of the headline, 30 minutes after, 1 hour after, and at the end of the day.
  - **Database Updates**: Updates the `news_signals` table with price data for each tracked interval.

## Testing
A suite of unit tests are located in the `tests` folder. Each script targets a specific module, ensuring code reliability and functionality:

- **`test_news_manager.py`**: Unit tests for the NewsManager module.
- **`test_price_fetcher.py`**: Unit tests for the PriceFetcher module.

The following command may be used to run all tests:

```bash
python -m unittest discover tests
```

## Version and Updates
- **Last Update**: November 15th, 2024
- **Version**: 1.0.0

Check the [CHANGELOG](CHANGELOG.md) for detailed updates and version history.

## Disclaimer
This project is for educational and informational purposes only. It is not intended as financial advice or an endorsement of any trading strategy. The trade recommendations and price data collected through this application are generated based on automated analysis and may not be accurate or reflect actual market movements.