from typing import Dict, List, Optional, Union, Any
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

# ---------- Watchlist Operations ----------

async def create_watchlist(name: str) -> bool:
    """Create a new watchlist with the given name"""
    try:
        collection = await get_finance_collection()
        
        # Check if watchlist already exists
        existing = await collection.find_one({"type": "watchlist", "name": name})
        if existing:
            logger.warning(f"Watchlist '{name}' already exists")
            return False
            
        # Create new watchlist
        await collection.insert_one({
            "type": "watchlist",
            "name": name,
            "tickers": []
        })
        
        return True
    except Exception as e:
        logger.error(f"Error creating watchlist: {e}")
        return False

async def delete_watchlist(name: str) -> bool:
    """Delete a watchlist by name"""
    try:
        collection = await get_finance_collection()
        
        result = await collection.delete_one({"type": "watchlist", "name": name})
        
        if result.deleted_count == 0:
            logger.warning(f"Watchlist '{name}' not found")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error deleting watchlist: {e}")
        return False

async def list_watchlists() -> List[str]:
    """Get names of all watchlists"""
    try:
        collection = await get_finance_collection()
        
        cursor = collection.find({"type": "watchlist"}, {"name": 1})
        watchlists = [doc.get("name") for doc in await cursor.to_list(length=100)]
        
        return watchlists
    except Exception as e:
        logger.error(f"Error listing watchlists: {e}")
        return []

async def get_watchlist(name: str) -> Optional[Dict]:
    """Get a watchlist by name"""
    try:
        collection = await get_finance_collection()
        
        watchlist = await collection.find_one({"type": "watchlist", "name": name})
        return watchlist
    except Exception as e:
        logger.error(f"Error getting watchlist: {e}")
        return None

async def add_tickers_to_watchlist(name: str, tickers: List[str]) -> bool:
    """Add stock tickers to a specific watchlist"""
    try:
        collection = await get_finance_collection()
        
        # Convert tickers to uppercase
        tickers = [ticker.upper() for ticker in tickers]
        
        # Update the watchlist, adding only unique tickers
        result = await collection.update_one(
            {"type": "watchlist", "name": name},
            {"$addToSet": {"tickers": {"$each": tickers}}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"Watchlist '{name}' not found")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error adding tickers to watchlist: {e}")
        return False

async def remove_tickers_from_watchlist(name: str, tickers: List[str]) -> bool:
    """Remove stock tickers from a specific watchlist"""
    try:
        collection = await get_finance_collection()
        
        # Convert tickers to uppercase
        tickers = [ticker.upper() for ticker in tickers]
        
        result = await collection.update_one(
            {"type": "watchlist", "name": name},
            {"$pullAll": {"tickers": tickers}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"Watchlist '{name}' not found")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error removing tickers from watchlist: {e}")
        return False

# ---------- Portfolio Operations ----------

async def create_portfolio(name: str) -> bool:
    """Create a new portfolio with the given name"""
    try:
        collection = await get_finance_collection()
        
        # Check if portfolio already exists
        existing = await collection.find_one({"type": "portfolio", "name": name})
        if existing:
            logger.warning(f"Portfolio '{name}' already exists")
            return False
            
        # Create new portfolio
        await collection.insert_one({
            "type": "portfolio",
            "name": name,
            "positions": []
        })
        
        return True
    except Exception as e:
        logger.error(f"Error creating portfolio: {e}")
        return False

async def delete_portfolio(name: str) -> bool:
    """Delete a portfolio by name"""
    try:
        collection = await get_finance_collection()
        
        result = await collection.delete_one({"type": "portfolio", "name": name})
        
        if result.deleted_count == 0:
            logger.warning(f"Portfolio '{name}' not found")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error deleting portfolio: {e}")
        return False

async def list_portfolios() -> List[str]:
    """Get names of all portfolios"""
    try:
        collection = await get_finance_collection()
        
        cursor = collection.find({"type": "portfolio"}, {"name": 1})
        portfolios = [doc.get("name") for doc in await cursor.to_list(length=100)]
        
        return portfolios
    except Exception as e:
        logger.error(f"Error listing portfolios: {e}")
        return []

async def get_portfolio(name: str) -> Optional[Dict]:
    """Get a portfolio by name"""
    try:
        collection = await get_finance_collection()
        
        portfolio = await collection.find_one({"type": "portfolio", "name": name})
        return portfolio
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return None

async def add_position_to_portfolio(name: str, symbol: str, price_paid: float, quantity: float) -> bool:
    """Add or update a position in a portfolio"""
    try:
        collection = await get_finance_collection()
        
        # Convert symbol to uppercase
        symbol = symbol.upper()
        
        # Check if position already exists in portfolio
        portfolio = await collection.find_one(
            {"type": "portfolio", "name": name, "positions.symbol": symbol}
        )
        
        if portfolio:
            # Update existing position
            result = await collection.update_one(
                {"type": "portfolio", "name": name, "positions.symbol": symbol},
                {"$set": {"positions.$.price_paid": price_paid, "positions.$.quantity": quantity}}
            )
        else:
            # Add new position
            result = await collection.update_one(
                {"type": "portfolio", "name": name},
                {"$push": {"positions": {"symbol": symbol, "price_paid": price_paid, "quantity": quantity}}}
            )
        
        if result.matched_count == 0:
            logger.warning(f"Portfolio '{name}' not found")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error adding position to portfolio: {e}")
        return False

async def remove_position_from_portfolio(name: str, symbol: str) -> bool:
    """Remove a position from a portfolio"""
    try:
        collection = await get_finance_collection()
        
        # Convert symbol to uppercase
        symbol = symbol.upper()
        
        result = await collection.update_one(
            {"type": "portfolio", "name": name},
            {"$pull": {"positions": {"symbol": symbol}}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"Portfolio '{name}' not found")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error removing position from portfolio: {e}")
        return False

# ---------- Legacy support functions ----------

async def initialize_stock_watchlist():
    """Initialize the default stock watchlist if it doesn't exist"""
    await create_watchlist("default")

async def add_stock_tickers(tickers: List[str]) -> bool:
    """Add stock tickers to the default watchlist (legacy support)"""
    return await add_tickers_to_watchlist("default", tickers)

async def remove_stock_tickers(tickers: List[str]) -> bool:
    """Remove stock tickers from the default watchlist (legacy support)"""
    return await remove_tickers_from_watchlist("default", tickers)

async def list_stock_tickers() -> List[str]:
    """Get all stock tickers from the default watchlist (legacy support)"""
    watchlist = await get_watchlist("default")
    if watchlist:
        return watchlist.get("tickers", [])
    return []

def get_tool_function_map():
    """Get the tool function map for stock-related functions"""
    tool_function_map = {
        # Legacy support functions
        "add_stock_tickers": {
            "function": add_stock_tickers,
            "description": "Add one or more stock tickers to the default watchlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of stock ticker symbols to add (e.g., ['AAPL', 'GOOGL'])",
                    }
                },
                "required": ["tickers"],
            },
        },
        "remove_stock_tickers": {
            "function": remove_stock_tickers,
            "description": "Remove one or more stock tickers from the default watchlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of stock ticker symbols to remove (e.g., ['AAPL', 'GOOGL'])",
                    }
                },
                "required": ["tickers"],
            },
        },
        "list_stock_tickers": {
            "function": list_stock_tickers,
            "description": "Get a list of all stock tickers in the default watchlist",
            "parameters": {
                "type": "object",
                "properties": {},  # No parameters needed
            },
        },
        
        # Watchlist functions
        "create_watchlist": {
            "function": create_watchlist,
            "description": "Create a new watchlist with the given name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the watchlist to create",
                    }
                },
                "required": ["name"],
            },
        },
        "delete_watchlist": {
            "function": delete_watchlist,
            "description": "Delete a watchlist by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the watchlist to delete",
                    }
                },
                "required": ["name"],
            },
        },
        "list_watchlists": {
            "function": list_watchlists,
            "description": "Get names of all watchlists",
            "parameters": {
                "type": "object",
                "properties": {},  # No parameters needed
            },
        },
        "get_watchlist": {
            "function": get_watchlist,
            "description": "Get a watchlist by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the watchlist to retrieve",
                    }
                },
                "required": ["name"],
            },
        },
        "add_tickers_to_watchlist": {
            "function": add_tickers_to_watchlist,
            "description": "Add stock tickers to a specific watchlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the watchlist to add tickers to",
                    },
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of stock ticker symbols to add (e.g., ['AAPL', 'GOOGL'])",
                    }
                },
                "required": ["name", "tickers"],
            },
        },
        "remove_tickers_from_watchlist": {
            "function": remove_tickers_from_watchlist,
            "description": "Remove stock tickers from a specific watchlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the watchlist to remove tickers from",
                    },
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of stock ticker symbols to remove (e.g., ['AAPL', 'GOOGL'])",
                    }
                },
                "required": ["name", "tickers"],
            },
        },
        
        # Portfolio functions
        "create_portfolio": {
            "function": create_portfolio,
            "description": "Create a new portfolio with the given name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the portfolio to create",
                    }
                },
                "required": ["name"],
            },
        },
        "delete_portfolio": {
            "function": delete_portfolio,
            "description": "Delete a portfolio by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the portfolio to delete",
                    }
                },
                "required": ["name"],
            },
        },
        "list_portfolios": {
            "function": list_portfolios,
            "description": "Get names of all portfolios",
            "parameters": {
                "type": "object",
                "properties": {},  # No parameters needed
            },
        },
        "get_portfolio": {
            "function": get_portfolio,
            "description": "Get a portfolio by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the portfolio to retrieve",
                    }
                },
                "required": ["name"],
            },
        },
        "add_position_to_portfolio": {
            "function": add_position_to_portfolio,
            "description": "Add or update a position in a portfolio",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the portfolio to add position to",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL')",
                    },
                    "price_paid": {
                        "type": "number",
                        "description": "Price paid per share",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Number of shares owned",
                    }
                },
                "required": ["name", "symbol", "price_paid", "quantity"],
            },
        },
        "remove_position_from_portfolio": {
            "function": remove_position_from_portfolio,
            "description": "Remove a position from a portfolio",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the portfolio to remove position from",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol to remove (e.g., 'AAPL')",
                    }
                },
                "required": ["name", "symbol"],
            },
        },
    }
    return tool_function_map