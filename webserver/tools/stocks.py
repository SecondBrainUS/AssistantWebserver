from typing import Dict, List
import logging
from webserver.db.chatdb.db import mongodb_client

logger = logging.getLogger(__name__)

INTRADAY_THRESHOLD = 5.0  # 5% change within a day
PERIOD_THRESHOLDS: Dict[int, float] = {
    3: 10.0,   # 10% change in 3 days
    7: 15.0,   # 15% change in 7 days
    30: 25.0,  # 25% change in 30 days
}

async def get_finance_collection():
    return await mongodb_client.get_collection("finance")

async def initialize_stock_watchlist():
    """Initialize the stock watchlist document if it doesn't exist"""
    collection = await get_finance_collection()
    watchlist = await collection.find_one({"type": "stock_watchlist"})
    if not watchlist:
        await collection.insert_one({
            "type": "stock_watchlist",
            "tickers": []
        })

async def add_stock_tickers(tickers: List[str]) -> bool:
    """Add stock tickers to the watchlist"""
    try:
        collection = await get_finance_collection()
        await initialize_stock_watchlist()
        
        # Convert tickers to uppercase and remove duplicates
        tickers = [ticker.upper() for ticker in tickers]
        
        # Update the watchlist, adding only unique tickers
        result = await collection.update_one(
            {"type": "stock_watchlist"},
            {"$addToSet": {"tickers": {"$each": tickers}}}
        )
        
        return True
    except Exception as e:
        logger.error(f"Error adding stock tickers: {e}")
        return False

async def remove_stock_tickers(tickers: List[str]) -> bool:
    """Remove stock tickers from the watchlist"""
    try:
        collection = await get_finance_collection()
        
        # Convert tickers to uppercase
        tickers = [ticker.upper() for ticker in tickers]
        
        result = await collection.update_one(
            {"type": "stock_watchlist"},
            {"$pullAll": {"tickers": tickers}}
        )
        
        return True
    except Exception as e:
        logger.error(f"Error removing stock tickers: {e}")
        return False

async def list_stock_tickers() -> List[str]:
    """Get all stock tickers from the watchlist"""
    try:
        collection = await get_finance_collection()
        await initialize_stock_watchlist()
        
        watchlist = await collection.find_one({"type": "stock_watchlist"})
        return watchlist.get("tickers", [])
    except Exception as e:
        logger.error(f"Error listing stock tickers: {e}")
        return []

def get_tool_function_map():
    """Get the tool function map for stock-related functions"""
    tool_function_map = {
        "add_stock_tickers": {
            "function": add_stock_tickers,
            "description": "Add one or more stock tickers to the watchlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                        "description": "Array of stock ticker symbols to add (e.g., ['AAPL', 'GOOGL'])",
                    }
                },
                "required": ["tickers"],
            },
        },
        "remove_stock_tickers": {
            "function": remove_stock_tickers,
            "description": "Remove one or more stock tickers from the watchlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                        "description": "Array of stock ticker symbols to remove (e.g., ['AAPL', 'GOOGL'])",
                    }
                },
                "required": ["tickers"],
            },
        },
        "list_stock_tickers": {
            "function": list_stock_tickers,
            "description": "Get a list of all stock tickers in the watchlist",
            "parameters": {
                "type": "object",
                "properties": {},  # No parameters needed
            },
        },
    }
    return tool_function_map