"""
BrightData Search Tool for Assistant Webserver

This module provides tools for searching the web and retrieving content using BrightData's services.
It acts as a bridge between the AssistantWebserver and the BrightData search module.
"""

import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from webserver.config import settings
from webserver.tools.brightdata_search import (
    BrightDataConfig, 
    BrightDataSearcher, 
    SearchQuery)

logger = logging.getLogger(__name__)

def get_brightdata_config() -> BrightDataConfig:
    """
    Create a BrightDataConfig object from settings.
    
    Returns:
        BrightDataConfig: Configuration for BrightData APIs
    """
    results_dir = Path("results/brightdata")
    results_dir.mkdir(exist_ok=True, parents=True)
    
    return BrightDataConfig(
        serp_api_key=settings.BRIGHT_DATA_SERP_API_KEY,
        unlocker_api_key=settings.BRIGHT_DATA_UNLOCKER_API_KEY,
        serp_zone=settings.BRIGHT_DATA_SERP_ZONE,
        unlocker_zone=settings.BRIGHT_DATA_UNLOCKER_ZONE,
        results_dir=results_dir
    )

async def brightdata_search(
    query: str, 
    result_count: int = 5, 
    location: str = "US", 
    language: str = "en", 
    scrape_content: bool = True
) -> Dict[str, Any]:
    """
    Search the web using BrightData's SERP API and retrieve content.
    
    Args:
        query: The search query
        result_count: Number of search results to retrieve
        location: Location for search results
        language: Language for search results
        scrape_content: Whether to scrape content from search results
        
    Returns:
        Dict with search results and metadata
    """
    try:
        # Get configuration
        config = get_brightdata_config()
        
        # Create searcher
        searcher = BrightDataSearcher(
            config=config,
            log_level=logging.INFO,
            log_to_file=True,
            log_file="brightdata_search.log"
        )
        
        # Create search query
        search_query = SearchQuery(
            query=query,
            result_count=result_count,
            location=location,
            language=language,
            format_type="raw"
        )
        
        # Perform search
        response = searcher.search(search_query, scrape_content=scrape_content)
        
        # Build a simple response with the most important information
        result = {
            "query": query,
            "timestamp": response.timestamp.isoformat(),
            "success": response.success,
            "total_results": len(response.search_results),
            "search_results": []
        }
        
        # Add search results
        for search_result in response.search_results:
            result["search_results"].append({
                "title": search_result.title,
                "url": search_result.link,
                "snippet": search_result.snippet
            })
        
        # Add content summaries if scraping was enabled
        if scrape_content and response.scraped_contents:
            result["scraped_content"] = []
            
            for content in response.scraped_contents:
                content_info = {
                    "title": content.title,
                    "url": content.url,
                    "success": content.success
                }
                
                if content.success:
                    # Include markdown content directly
                    content_info["markdown"] = content.markdown_content
                else:
                    content_info["error"] = content.error
                    
                result["scraped_content"].append(content_info)
        
        return result
    
    except Exception as e:
        logger.error(f"Error in brightdata_search: {str(e)}")
        return {
            "error": str(e),
            "success": False
        }

async def brightdata_get_content(url: str, render_js: bool = True) -> Dict[str, Any]:
    """
    Retrieve content from a specific URL using BrightData's Web Unlocker API.
    
    Args:
        url: The URL to retrieve content from
        render_js: Whether to render JavaScript on the page
        
    Returns:
        Dict with page content
    """
    try:
        # Input validation
        if not url or not url.strip():
            return {
                "url": url if url else "",
                "error": "Empty URL provided",
                "success": False
            }
            
        if not url.startswith(('http://', 'https://')):
            return {
                "url": url,
                "error": "Invalid URL format. URL must start with http:// or https://",
                "success": False
            }
            
        # Get configuration
        config = get_brightdata_config()
        
        # Create searcher
        searcher = BrightDataSearcher(
            config=config,
            log_level=logging.INFO,
            log_to_file=True,
            log_file="brightdata_content.log"
        )
        
        # Get content
        try:
            html_content, markdown_content = searcher.get_page_content(
                url=url,
                render_js=render_js,
                format_type="raw"
            )
            
            # Check if the markdown content is meaningful
            if not markdown_content or not markdown_content.strip():
                logger.warning(f"Retrieved empty markdown content from {url}")
                return {
                    "url": url,
                    "error": "Retrieved content is empty",
                    "success": False,
                    "html_length": len(html_content) if html_content else 0
                }
                
            # Return content
            return {
                "url": url,
                "success": True,
                "markdown": markdown_content,
                "content_length": len(markdown_content)
            }
        except Exception as content_error:
            logger.error(f"Error retrieving content from {url}: {str(content_error)}")
            error_details = str(content_error)
            
            # Provide more user-friendly error messages for common cases
            if "403" in error_details:
                error_message = f"Access forbidden (403). The site may be blocking access: {error_details}"
            elif "404" in error_details:
                error_message = f"Page not found (404): {error_details}"
            elif "timeout" in error_details.lower():
                error_message = f"Request timed out. The site may be slow or blocking access: {error_details}"
            elif "certificate" in error_details.lower():
                error_message = f"SSL certificate error. The site may have security issues: {error_details}"
            else:
                error_message = error_details
                
            return {
                "url": url,
                "error": error_message,
                "success": False
            }
        
    except Exception as e:
        logger.error(f"Unexpected error in brightdata_get_content: {str(e)}")
        return {
            "url": url,
            "error": f"Unexpected error: {str(e)}",
            "success": False
        }

def get_tool_function_map():
    """
    Get the tool function map for BrightData-related functions.
    
    Returns:
        Dict[str, Dict]: A dictionary mapping tool names to their function details.
    """
    return {
        "brightdata_search": {
            "function": brightdata_search,
            "description": "Search the web using BrightData's SERP API and retrieve content from search results.",
            "system_prompt_description": "Use brightdata_search to perform web searches and retrieve current information from the internet. Useful for researching topics, finding news, or getting information about events, companies, or people.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to perform",
                    },
                    "result_count": {
                        "type": "integer",
                        "description": "Number of search results to retrieve (default: 5)",
                        "default": 5,
                    },
                    "location": {
                        "type": "string",
                        "description": "Location for search results (e.g., 'US', 'UK', 'DE')",
                        "default": "US",
                    },
                    "language": {
                        "type": "string",
                        "description": "Language for search results (e.g., 'en', 'fr', 'de')",
                        "default": "en",
                    },
                    "scrape_content": {
                        "type": "boolean",
                        "description": "Whether to scrape content from search results",
                        "default": True,
                    }
                },
                "required": ["query"],
            },
        },
        "brightdata_get_content": {
            "function": brightdata_get_content,
            "description": "Retrieve content from a specific URL using BrightData's Web Unlocker API.",
            "system_prompt_description": "Use brightdata_get_content to retrieve and view the full content of a specific webpage. Useful when you need to analyze or extract information from a particular website.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to retrieve content from",
                    },
                    "render_js": {
                        "type": "boolean",
                        "description": "Whether to render JavaScript on the page",
                        "default": True,
                    }
                },
                "required": ["url"],
            },
        }
    } 