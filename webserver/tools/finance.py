import logging
from datetime import datetime, timedelta
from typing import Optional, List
import yfinance as yf

logger = logging.getLogger(__name__)

def get_stock_data(tickers: List[str]) -> dict:
    """
    Fetch current price and percentage changes for given stock tickers.
    
    :param tickers: List of stock ticker symbols
    :return: Dictionary with stock data for each ticker
    """
    try:
        stock_data = YahooFinanceStockData(tickers)
        stock_data.fetch_data()
        return stock_data.data
    except Exception as e:
        logger.error(f"Error fetching stock data: {str(e)}")
        raise Exception(f"Failed to fetch stock data: {str(e)}") from e

def get_current_stock_price(ticker: str) -> Optional[float]:
    """
    Get the current price for a single stock ticker.
    
    :param ticker: Stock ticker symbol
    :return: Current stock price or None if unavailable
    """
    try:
        stock = yf.Ticker(ticker)
        today_data = stock.history(period='1d')
        if not today_data.empty:
            return float(today_data['Close'].iloc[-1])
        
        info = stock.info
        if info.get('regularMarketPrice'):
            return float(info['regularMarketPrice'])
            
        logger.warning(f"No price data available for {ticker}")
        return None
    except Exception as e:
        logger.error(f"Error fetching price for {ticker}: {str(e)}")
        return None

def get_tool_function_map():
    """Get the tool function map for finance-related functions"""
    tool_function_map = {
        "finance_get_stock_data": {
            "function": get_stock_data,
            "description": "Get current price and percentage changes for multiple stock tickers",
            "system_prompt_description": "Use finance_get_stock_data to fetch current prices and percentage changes for stocks. Provide a list of ticker symbols.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of stock ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOG'])",
                    },
                },
                "required": ["tickers"],
            },
        },
        "finance_get_current_stock_price": {
            "function": get_current_stock_price,
            "description": "Get the current price for a single stock ticker",
            "system_prompt_description": "Use finance_get_current_stock_price to get the latest price for a single stock. Provide a ticker symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL')",
                    },
                },
                "required": ["ticker"],
            },
        },
    }
    return tool_function_map

class YahooFinanceStockData:
    """Implementation of YahooFinanceStockData class from the original finance.py"""
    def __init__(self, tickers):
        self.tickers_list = tickers
        self.data = {}
        self.periods = [3, 7, 14, 30, 90, 180]
        self.yf = yf
        self.ticker_objects = {ticker: yf.Ticker(ticker) for ticker in tickers}
        self.historical_data = {}
        self.today = datetime.now().date()
        self.start_date = self.today - timedelta(days=max(self.periods) + 10)

        for ticker in tickers:
            self.historical_data[ticker] = self.ticker_objects[ticker].history(
                start=self.start_date, end=self.today
            )

    def get_current_price(self, ticker):
        """
        Gets the current price of the ticker.

        Parameters:
        ticker (str): The ticker symbol.

        Returns:
        float: The current price.
        """
        historical_data = self.historical_data[ticker]
        if historical_data.empty:
            return None
        return historical_data['Close'].iloc[-1]

    def get_price_at_date(self, ticker, date):
        """
        Gets the price of the ticker at the nearest previous trading day to the given date.

        Parameters:
        ticker (str): The ticker symbol.
        date (datetime.date): The target date.

        Returns:
        float: The price at the nearest previous trading day.
        """
        historical_data = self.historical_data[ticker]
        price_series = historical_data.loc[historical_data.index.date == date]['Close']
        if price_series.empty:
            return None
        return price_series.iloc[0]

    def get_nearest_previous_trading_day(self, ticker, target_date):
        """
        Finds the nearest previous trading day for the ticker.

        Parameters:
        ticker (str): The ticker symbol.
        target_date (datetime.date): The target date.

        Returns:
        datetime.date or None: The date of the nearest previous trading day, or None if not found.
        """
        trading_days = self.historical_data[ticker].index.date
        while target_date not in trading_days:
            target_date -= timedelta(days=1)
            if target_date < self.start_date:
                return None
        return target_date

    @staticmethod
    def calculate_percentage_change(current, previous):
        """
        Calculates the percentage change between two prices.

        Parameters:
        current (float): The current price.
        previous (float): The previous price.

        Returns:
        float: The percentage change rounded to two decimals.
        """
        if previous == 0 or previous is None:
            return 0.0
        change = ((current - previous) / previous) * 100
        return round(change, 2)

    def fetch_data(self):
        """
        Fetches data for each ticker and calculates percentage changes.
        Skips tickers that return no data.
        """
        for ticker in self.tickers_list:
            current_price = self.get_current_price(ticker)
            if current_price is None:
                logger.warning(f"Skipping {ticker} due to no available price data")
                self.data[ticker] = {
                    'current_price': None,
                    'error': 'No price data available - ticker may be delisted or invalid'
                }
                continue
                
            result = {'current_price': round(current_price, 2)}
            today = datetime.now().date()

            for period in self.periods:
                target_date = today - timedelta(days=period)
                target_date = self.get_nearest_previous_trading_day(ticker, target_date)
                if target_date is None:
                    percent_change = 0.0
                else:
                    previous_price = self.get_price_at_date(ticker, target_date)
                    percent_change = self.calculate_percentage_change(
                        current_price, previous_price
                    )
                result[f'percent_change_{period}_days'] = percent_change

            self.data[ticker] = result

    def get_intraday_change(self, ticker: str) -> float:
        """Calculate the intraday percentage change."""
        historical_data = self.historical_data[ticker]
        if len(historical_data) < 1:
            return 0.0
        
        current_price = historical_data['Close'].iloc[-1]
        open_price = historical_data['Open'].iloc[-1]
        
        return self.calculate_percentage_change(current_price, open_price)


if __name__ == "__main__":
    # Test the functionality
    tickers = ['MSFT', 'AAPL', 'GOOG']
    try:
        print("\nTesting get_stock_data():")
        result = get_stock_data(tickers)
        print(f"Stock data: {result}")

        print("\nTesting get_current_stock_price():")
        price = get_current_stock_price('AAPL')
        print(f"Current AAPL price: {price}")
    except Exception as e:
        print(f"Error during testing: {str(e)}") 