import requests
import json
import logging
import difflib
from typing import Optional, Dict, List, Any
from webserver.config import settings

logger = logging.getLogger(__name__)

class NotionClient:
    def __init__(self):
        self.api_key = settings.NOTION_API_KEY
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def get_database_properties(self, database_id: str) -> dict:
        """Get properties of a Notion database"""
        url = f"{self.base_url}/databases/{database_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get database properties: {response.text}")
            raise Exception(f"Failed to get database properties: {response.text}")

    def search_database_by_name(self, database_name: str) -> Optional[dict]:
        """Search for a database by name using fuzzy matching"""
        url = f"{self.base_url}/search"
        data = {
            "filter": {"property": "object", "value": "database"},
            "query": database_name
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code != 200:
            logger.error(f"Failed to search database: {response.text}")
            raise Exception(f"Failed to search database: {response.text}")
            
        results = response.json().get("results", [])
        if not results:
            return None
            
        # Use fuzzy matching to find best match
        best_match = None
        best_score = 0
        
        for db in results:
            title = db.get("title", [{}])[0].get("plain_text", "")
            score = difflib.SequenceMatcher(None, database_name.lower(), title.lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = db
                
        return best_match if best_score > 0.5 else None

    def get_database(self, database_id: str) -> dict:
        """Get a database by its ID"""
        url = f"{self.base_url}/databases/{database_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get database: {response.text}")
            raise Exception(f"Failed to get database: {response.text}")

    def query_database(self, database_id: str, filter_dict: Optional[dict] = None) -> List[dict]:
        """Get items from a database with optional filters"""
        url = f"{self.base_url}/databases/{database_id}/query"
        data = {"filter": filter_dict} if filter_dict else {}
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            logger.error(f"Failed to query database: {response.text}")
            raise Exception(f"Failed to query database: {response.text}")

    def add_item(self, database_id: str, properties: dict) -> dict:
        """Add a new item to a database"""
        url = f"{self.base_url}/pages"
        data = {
            "parent": {"database_id": database_id},
            "properties": properties
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to add item: {response.text}")
            raise Exception(f"Failed to add item: {response.text}")

    def list_databases(self) -> List[dict]:
        """List all accessible databases"""
        url = f"{self.base_url}/search"
        data = {
            "filter": {
                "property": "object",
                "value": "database"
            }
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            logger.error(f"Failed to list databases: {response.text}")
            raise Exception(f"Failed to list databases: {response.text}")

# Create a global Notion client
notion_client = NotionClient()

def get_database_properties(database_id: str) -> dict:
    return notion_client.get_database_properties(database_id)

def search_database_by_name(database_name: str) -> Optional[dict]:
    return notion_client.search_database_by_name(database_name)

def get_database(database_id: str) -> dict:
    return notion_client.get_database(database_id)

def query_database(database_id: str, filter_dict: Optional[dict] = None) -> List[dict]:
    return notion_client.query_database(database_id, filter_dict)

def add_item(database_id: str, properties: dict) -> dict:
    return notion_client.add_item(database_id, properties)

def list_databases() -> List[dict]:
    return notion_client.list_databases()

def get_tool_function_map():
    """Get the tool function map for Notion-related functions"""
    return {
        "notion_get_database_properties": {
            "function": get_database_properties,
            "description": "Get properties of a Notion database",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "ID of the Notion database"
                    }
                },
                "required": ["database_id"]
            }
        },
        "notion_search_database": {
            "function": search_database_by_name,
            "description": "Search for a Notion database by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_name": {
                        "type": "string",
                        "description": "Name of the database to search for"
                    }
                },
                "required": ["database_name"]
            }
        },
        "notion_get_database": {
            "function": get_database,
            "description": "Get a Notion database by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "ID of the database to retrieve"
                    }
                },
                "required": ["database_id"]
            }
        },
        "notion_query_database": {
            "function": query_database,
            "description": "Query items from a Notion database",
            "system_prompt_description": ("Use notion_query_database to filter and sort database items. The filter_dict must follow Notion's filter structure. "
                                        "Example of a compound filter with sorting:\n"
                                        "{\n"
                                        "  \"filter\": {\n"
                                        "    \"and\": [\n"
                                        "      {\n"
                                        "        \"property\": \"Do Level\",\n"
                                        "        \"select\": {\n"
                                        "          \"does_not_equal\": \"Could Do\"\n"
                                        "        }\n"
                                        "      },\n"
                                        "      {\n"
                                        "        \"property\": \"Priority\",\n"
                                        "        \"select\": {\n"
                                        "          \"is_not_empty\": true\n"
                                        "        }\n"
                                        "      }\n"
                                        "    ]\n"
                                        "  },\n"
                                        "  \"sorts\": [\n"
                                        "    {\n"
                                        "      \"property\": \"Sort Order\",\n"
                                        "      \"direction\": \"ascending\"\n"
                                        "    },\n"
                                        "    {\n"
                                        "      \"property\": \"Priority\",\n"
                                        "      \"direction\": \"ascending\"\n"
                                        "    },\n"
                                        "    {\n"
                                        "      \"property\": \"Do on\",\n"
                                        "      \"direction\": \"ascending\"\n"
                                        "    }\n"
                                        "  ]\n"
                                        "}\n"),
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "ID of the database to query"
                    },
                    "filter_dict": {
                        "type": "object",
                        "description": """Filter criteria. The filter must follow Notion's filter structure. Examples:
                        Single filter: 
                        {
                            "property": "Done",
                            "checkbox": {
                                "equals": true
                            }
                        }
                        
                        Compound filter:
                        {
                            "and": [
                                {
                                    "property": "Done",
                                    "checkbox": {
                                        "equals": true
                                    }
                                },
                                {
                                    "or": [
                                        {
                                            "property": "Tags",
                                            "contains": "A"
                                        },
                                        {
                                            "property": "Tags",
                                            "contains": "B"
                                        }
                                    ]
                                }
                            ]
                        }""",
                    }
                },
                "required": ["database_id", "filter_dict"]
            }
        },
        "notion_add_item": {
            "function": add_item,
            "description": "Add a new item to a Notion database",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "ID of the database to add item to"
                    },
                    "properties": {
                        "type": "object",
                        "description": "Properties of the item to add"
                    }
                },
                "required": ["database_id", "properties"]
            }
        },
        "notion_list_databases": {
            "function": list_databases,
            "description": "List all accessible Notion databases",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    } 