"""
BrightData Search Module

This module provides a clean, reusable interface for performing web searches and content retrieval
using BrightData's SERP API and Web Unlocker API.

The module is designed to be parameterized, flexible, and provide detailed information about
the querying process, including success/failure metrics.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
from datetime import datetime
import tempfile
import re
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup, Comment
from markitdown import MarkItDown
from dataclasses import dataclass, field, asdict

# Configure logging
logger = logging.getLogger("brightdata_search")

@dataclass
class BrightDataConfig:
    """Configuration for BrightData APIs"""
    serp_api_key: str
    unlocker_api_key: str
    serp_zone: str
    unlocker_zone: str
    results_dir: Path = Path("results")
    
    def __post_init__(self):
        """Ensure the results directory exists"""
        self.results_dir.mkdir(exist_ok=True, parents=True)

@dataclass
class SearchQuery:
    """Represents a search query and its parameters"""
    query: str
    result_count: int = 10
    location: Optional[str] = None
    language: Optional[str] = None
    device: Optional[str] = None
    render_js: bool = True
    format_type: str = "raw"  # "raw" or "json"
    extra_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchResult:
    """Represents a single search result"""
    title: str
    link: str
    position: int
    snippet: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass 
class ScrapedContent:
    """Represents scraped content from a web page"""
    title: str
    url: str
    position: int
    html_content: Optional[str] = None
    markdown_content: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SearchResponse:
    """Represents the complete response for a search query"""
    query: str
    timestamp: datetime = field(default_factory=datetime.now)
    search_results: List[SearchResult] = field(default_factory=list)
    scraped_contents: List[ScrapedContent] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "search_results": [asdict(r) for r in self.search_results],
            "scraped_contents": [asdict(c) for c in self.scraped_contents],
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata
        }
    
    def summary(self) -> Dict[str, Any]:
        """Generate a summary of the search response"""
        return {
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "error": self.error,
            "num_results": len(self.search_results),
            "num_scraped": len(self.scraped_contents),
            "num_scraped_successful": sum(1 for c in self.scraped_contents if c.success),
            "num_scraped_failed": sum(1 for c in self.scraped_contents if not c.success)
        }


class BrightDataSearcher:
    """
    Main class for performing web searches and content retrieval using BrightData APIs.
    """
    
    def __init__(
        self, 
        config: BrightDataConfig,
        log_level: int = logging.INFO,
        log_to_file: bool = True,
        log_file: Optional[str] = "brightdata_search.log"
    ):
        """
        Initialize the BrightDataSearcher.
        
        Args:
            config: BrightDataConfig object with API keys and zones
            log_level: Logging level (default: INFO)
            log_to_file: Whether to log to a file (default: True)
            log_file: Log file name (default: "brightdata_search.log")
        """
        self.config = config
        self._setup_logging(log_level, log_to_file, log_file)
        self._exceptions_file = config.results_dir / "exceptions_web_unlocker.json"
        
        # Ensure exceptions file parent directory exists
        self._exceptions_file.parent.mkdir(exist_ok=True, parents=True)
    
    def _setup_logging(self, log_level: int, log_to_file: bool, log_file: Optional[str]) -> None:
        """
        Set up logging configuration.
        
        Args:
            log_level: Logging level
            log_to_file: Whether to log to a file
            log_file: Log file name
        """
        logger.setLevel(log_level)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Add console handler to logger
        logger.addHandler(console_handler)
        
        # If logging to file is enabled
        if log_to_file and log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
    
    def _create_query_dir(self, query: str) -> Path:
        """
        Create a sanitized folder name for a query and ensure the directory exists.
        
        Args:
            query: The search query
            
        Returns:
            Path to the query-specific directory
        """
        # Sanitize the query for use as a folder name
        sanitized_query = re.sub(r'[^a-zA-Z0-9]', '_', query)[:50].strip('_')
        
        # Add timestamp to make the folder unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{sanitized_query}_{timestamp}"
        
        # Create the folder path
        query_dir = self.config.results_dir / folder_name
        query_dir.mkdir(exist_ok=True)
        
        logger.info(f"Created query directory: {query_dir}")
        return query_dir
    
    def _read_exceptions_file(self) -> List[Dict[str, Any]]:
        """
        Read the exceptions file if it exists.
        
        Returns:
            List of failed access attempts
        """
        if not self._exceptions_file.exists():
            return []
        
        try:
            with open(self._exceptions_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Error reading {self._exceptions_file}. Creating new exceptions file.")
            return []
    
    def _append_to_exceptions_file(self, url: str, error: str) -> None:
        """
        Append a failed web unlocker attempt to the exceptions file.
        
        Args:
            url: The URL that failed to load
            error: The error message
        """
        exceptions = self._read_exceptions_file()
        
        exceptions.append({
            "url": url,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
        
        with open(self._exceptions_file, "w", encoding="utf-8") as f:
            json.dump(exceptions, f, indent=2)
        
        logger.info(f"Added failed URL to {self._exceptions_file}: {url}")
    
    def _clean_html_for_markdown(self, html_content: str) -> str:
        """
        Clean HTML by removing CSS, JavaScript, and other unnecessary elements
        before converting to Markdown. This preprocessing reduces token usage
        and improves the quality of the Markdown output for LLMs.
        
        Args:
            html_content (str): Raw HTML content
            
        Returns:
            str: Cleaned HTML content
        """
        try:
            # Parse HTML - attempt to handle malformed HTML gracefully
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
            except Exception as e:
                logger.warning(f"Error parsing HTML with BeautifulSoup: {str(e)}. Attempting to continue with partial parsing.")
                # Try with a more lenient parser that handles malformed HTML
                soup = BeautifulSoup(html_content, 'html5lib') if 'html5lib' in BeautifulSoup.builder_registry.keys() else BeautifulSoup(html_content, 'html.parser')
            
            # Remove all <style> tags
            for style in soup.find_all('style'):
                if style:  # Check if not None
                    style.decompose()
            
            # Remove all <link> tags with rel="stylesheet"
            for link in soup.find_all('link'):
                if link and link.has_attr('rel') and 'stylesheet' in link.get('rel', []):
                    link.decompose()
            
            # Remove all <script> tags
            for script in soup.find_all('script'):
                if script:  # Check if not None
                    script.decompose()
            
            # Remove style attributes from all tags
            for tag in soup.find_all(True):
                if not tag:  # Skip if tag is None
                    continue
                    
                # Remove style attribute
                if tag.has_attr('style'):
                    del tag['style']
                
                # Remove data attributes (data-*)
                attrs_to_remove = []
                for attr in tag.attrs:
                    if attr and attr.startswith('data-'):
                        attrs_to_remove.append(attr)
                
                for attr in attrs_to_remove:
                    del tag[attr]
                
                # Remove class attributes (often CSS-related)
                if tag.has_attr('class'):
                    del tag['class']
            
            # Remove JavaScript event handlers (onclick, onload, etc.)
            js_attrs = [
                'onclick', 'onchange', 'onmouseover', 'onmouseout', 
                'onkeydown', 'onload', 'onerror', 'onblur', 'onfocus',
                'onsubmit', 'onreset', 'onselect', 'onunload'
            ]
            
            for tag in soup.find_all(True):
                if not tag:  # Skip if tag is None
                    continue
                    
                for attr in js_attrs:
                    if tag.has_attr(attr):
                        del tag[attr]
            
            # Remove comments
            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                if comment:  # Check if not None
                    comment.extract()
            
            # Remove <meta> tags
            for meta in soup.find_all('meta'):
                if meta:  # Check if not None
                    meta.decompose()
            
            # Remove other unnecessary tags
            unnecessary_tags = ['svg', 'canvas', 'noscript', 'head', 'iframe', 'video', 'audio', 'aside', 'footer', 'nav']
            for tag_name in unnecessary_tags:
                for tag in soup.find_all(tag_name):
                    if tag:  # Check if not None
                        tag.decompose()
                    
            # Remove tracking and ad-related divs (common patterns)
            ad_classes = ['ad', 'ads', 'advertisement', 'banner', 'sponsor', 'tracking', 'analytics']
            for tag in soup.find_all('div'):
                if not tag:  # Skip if tag is None
                    continue
                    
                if tag.has_attr('id'):
                    id_value = tag.get('id')
                    if id_value:  # Check if id attribute is not None
                        id_lower = id_value.lower()
                        if any(pattern in id_lower for pattern in ad_classes):
                            tag.decompose()
            
            # Remove images with tracking URLs or decorative images
            for img in soup.find_all('img'):
                if not img:  # Skip if img is None
                    continue
                    
                # Keep the image if it has alt text (likely meaningful)
                alt_text = img.get('alt')
                if not alt_text or alt_text.strip() == '':
                    # Remove decorative images and tracking pixels
                    width = img.get('width')
                    height = img.get('height')
                    
                    if not width or not height:
                        img.decompose()
                    elif width == '1' or height == '1':
                        img.decompose()
            
            # Optional: Remove empty tags (tags with no content)
            for tag in soup.find_all():
                if not tag:  # Skip if tag is None
                    continue
                    
                # Handle potential errors in get_text()
                try:
                    text_content = tag.get_text(strip=True)
                    has_children = bool(tag.find_all())
                    if len(text_content) == 0 and not has_children:
                        tag.decompose()
                except Exception as e:
                    logger.warning(f"Error checking tag content: {str(e)}")
            
            # Clean up common web annoyances that add little value to content
            # Cookie notices, popups, newsletter signups, etc.
            popup_terms = ['cookie', 'subscribe', 'newsletter', 'signup', 'sign-up', 'accept', 'privacy']
            for div in soup.find_all(['div', 'section']):
                if not div:  # Skip if div is None
                    continue
                    
                try:
                    text = div.get_text().lower()
                    if any(term in text for term in popup_terms) and len(text) < 200:
                        if any(prompt in text for prompt in ['accept cookies', 'privacy policy', 'subscribe', 'sign up']):
                            div.decompose()
                except Exception as e:
                    logger.warning(f"Error processing div content: {str(e)}")
            
            # Return the cleaned HTML as a string
            return str(soup)
            
        except Exception as e:
            logger.error(f"Error in _clean_html_for_markdown: {str(e)}")
            # Return the original HTML if cleaning fails
            return html_content
    
    def _convert_html_to_markdown(self, html_content: str) -> str:
        """
        Converts HTML content to Markdown using MarkItDown.
        First cleans the HTML to remove unnecessary elements.
        Then applies post-processing to optimize the Markdown for LLM token usage.
        
        Args:
            html_content: Full HTML content as a string
        
        Returns:
            The Markdown text as a string
        """
        # Safety check for empty content
        if not html_content or not html_content.strip():
            logger.warning("Empty HTML content received for conversion")
            return ""
            
        # Initialize temp file to None for proper cleanup in finally block
        tmp_filepath = None
        
        try:
            # Measure original content size
            original_size = len(html_content)
            
            # Clean the HTML first
            logger.debug("Cleaning HTML before conversion to Markdown")
            cleaned_html = self._clean_html_for_markdown(html_content)
            
            # Measure cleaned HTML size
            cleaned_size = len(cleaned_html)
            html_reduction = (1 - cleaned_size / original_size) * 100 if original_size > 0 else 0
            logger.info(f"HTML cleaning reduced content size by {html_reduction:.2f}% (from {original_size} to {cleaned_size} characters)")
            
            # Safety check in case cleaning failed and returned empty content
            if not cleaned_html or not cleaned_html.strip():
                logger.warning("HTML cleaning resulted in empty content, using original HTML")
                cleaned_html = html_content
            
            # Write the cleaned HTML content to a temporary file
            try:
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".html", encoding="utf-8") as tmp_file:
                    tmp_file.write(cleaned_html)
                    tmp_filepath = tmp_file.name
            except Exception as e:
                logger.error(f"Error creating temporary file: {str(e)}")
                # Fall back to direct conversion without temp file if possible
                raise
    
            # Convert HTML to Markdown
            try:
                md = MarkItDown()
                result = md.convert(tmp_filepath)
                markdown_text = result.text_content
                
                # Safety check for conversion result
                if not markdown_text or not markdown_text.strip():
                    logger.warning("MarkItDown conversion resulted in empty content")
                    # Try basic fallback conversion if the result is empty
                    markdown_text = f"# Content from {tmp_filepath}\n\n" + cleaned_html
            except Exception as e:
                logger.error(f"Error in MarkItDown conversion: {str(e)}")
                # Create a basic conversion as fallback
                markdown_text = "# Content Conversion Error\n\n"
                markdown_text += "The content could not be properly converted to Markdown.\n\n"
                markdown_text += "## Raw Text Content\n\n"
                
                # Extract just text from HTML as a minimal fallback
                try:
                    soup = BeautifulSoup(cleaned_html, 'html.parser')
                    markdown_text += soup.get_text(separator="\n\n")
                except Exception as fallback_error:
                    logger.error(f"Even fallback text extraction failed: {str(fallback_error)}")
                    markdown_text += "Failed to extract text content."
                
                # Early return since we can't do further processing
                return markdown_text
            
            # Measure raw markdown size
            raw_markdown_size = len(markdown_text)
            
            # Post-processing to optimize the Markdown for LLMs
            try:
                # 1. Remove excess newlines
                markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
                
                # 2. Remove HTML comments that might have been missed
                markdown_text = re.sub(r'<!--.*?-->', '', markdown_text, flags=re.DOTALL)
                
                # 3. Remove any remaining HTML tags
                markdown_text = re.sub(r'<[^>]*>', '', markdown_text)
                
                # 4. Fix broken Markdown headings (ensure space after #)
                markdown_text = re.sub(r'(#+)([^ \n])', r'\1 \2', markdown_text)
                
                # 5. Clean up excessive horizontal rules
                markdown_text = re.sub(r'(\n---+\n)\s*(\n---+\n)', r'\1', markdown_text)
                
                # 6. Clean up URLs that may have been double-escaped or broken
                markdown_text = re.sub(r'\\\[(.*?)\\\]\\\((.*?)\\\)', r'[\1](\2)', markdown_text)
                
                # 7. Remove empty table rows and simplify tables with mostly empty cells
                if '|' in markdown_text:
                    lines = markdown_text.split('\n')
                    filtered_lines = []
                    in_table = False
                    empty_row_count = 0
                    
                    for line in lines:
                        if re.match(r'^\s*\|', line):  # Line starts with a table cell
                            in_table = True
                            # Check if the row is mostly empty cells
                            cells = re.findall(r'\|(.*?)', line)
                            empty_cells = sum(1 for cell in cells if cell.strip() in ('', '-'))
                            
                            if empty_cells > len(cells) * 0.7:  # If more than 70% cells are empty
                                empty_row_count += 1
                                if empty_row_count > 2:  # Skip if we've seen too many empty rows
                                    continue
                            else:
                                empty_row_count = 0
                        else:
                            in_table = False
                            empty_row_count = 0
                        
                        filtered_lines.append(line)
                    
                    markdown_text = '\n'.join(filtered_lines)
                
                # 8. Collapse consecutive duplicate lines (often happens with list items from menus)
                lines = markdown_text.split('\n')
                prev_line = None
                filtered_lines = []
                consecutive_count = 0
                
                for line in lines:
                    if line == prev_line:
                        consecutive_count += 1
                        if consecutive_count > 2:  # Only keep the first few duplicates
                            continue
                    else:
                        consecutive_count = 0
                    
                    filtered_lines.append(line)
                    prev_line = line
                
                markdown_text = '\n'.join(filtered_lines)
            except Exception as e:
                logger.error(f"Error in Markdown post-processing: {str(e)}")
                # If post-processing fails, continue with the unprocessed markdown
            
            # Measure optimized markdown size (even if optimization failed)
            optimized_size = len(markdown_text)
            md_reduction = (1 - optimized_size / raw_markdown_size) * 100 if raw_markdown_size > 0 else 0
            total_reduction = (1 - optimized_size / original_size) * 100 if original_size > 0 else 0
            
            # Log size reductions
            logger.info(f"Markdown optimization reduced size by an additional {md_reduction:.2f}% (from {raw_markdown_size} to {optimized_size} characters)")
            logger.info(f"Total size reduction: {total_reduction:.2f}% (from {original_size} to {optimized_size} characters)")
            
            # Estimate token reduction (rough approximation: ~4 chars per token for English text)
            estimated_tokens_saved = (original_size - optimized_size) / 4
            logger.info(f"Estimated tokens saved: ~{estimated_tokens_saved:.0f} tokens")
            
            logger.debug("Successfully converted and optimized HTML to Markdown")
            return markdown_text
            
        except Exception as e:
            logger.error(f"Unhandled error in HTML to Markdown conversion: {str(e)}")
            # Return a graceful error message with minimal content
            return f"# Error Converting Content\n\nThere was an error processing the web content:\n\n`{str(e)}`\n\nPlease try again with a different URL or contact support if the issue persists."
            
        finally:
            # Clean up the temporary file
            if tmp_filepath and os.path.exists(tmp_filepath):
                try:
                    os.remove(tmp_filepath)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {tmp_filepath}: {str(e)}")
    
    def _write_to_file(self, content: str, output_filepath: Path) -> None:
        """
        Writes content to a file.
        
        Args:
            content: Content as a string
            output_filepath: Destination file path
        """
        # Ensure the parent directory exists
        output_filepath.parent.mkdir(exist_ok=True, parents=True)
        
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Content written to {output_filepath}")
    
    def search(self, search_query: SearchQuery, scrape_content: bool = True) -> SearchResponse:
        """
        Performs a search using BrightData SERP API and optionally scrapes the content of search results.
        
        Args:
            search_query: SearchQuery object with query and parameters
            scrape_content: Whether to scrape content from search results (default: True)
            
        Returns:
            SearchResponse object with search results and scraped content
        """
        try:
            logger.info(f"Searching for: {search_query.query}")
            
            # Create response object
            response = SearchResponse(query=search_query.query)
            
            # Create a query-specific folder
            query_dir = self._create_query_dir(search_query.query)
            response.metadata["query_dir"] = str(query_dir)
            
            # Get search results
            search_results = self._get_serp_results(search_query, query_dir)
            
            # Process search results
            if not search_results:
                logger.warning("No search results found.")
                response.success = False
                response.error = "No search results found"
                return response
            
            # Convert search results to SearchResult objects
            for idx, result in enumerate(search_results, start=1):
                title = result.get("title", f"Result {idx}")
                link = result.get("link", "")
                
                if not link:
                    continue
                
                search_result = SearchResult(
                    title=title,
                    link=link,
                    position=idx,
                    snippet=result.get("snippet"),
                    metadata=result
                )
                
                response.search_results.append(search_result)
            
            # Scrape content if requested
            if scrape_content:
                for search_result in response.search_results:
                    scraped_content = self._scrape_content(
                        search_result,
                        search_query,
                        query_dir
                    )
                    response.scraped_contents.append(scraped_content)
            
            # Save summary inside the query directory
            summary_file = query_dir / "summary.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(response.to_dict(), f, indent=2)
            
            logger.info(f"Summary saved to {summary_file}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error in search process: {str(e)}")
            response = SearchResponse(
                query=search_query.query,
                success=False,
                error=str(e)
            )
            return response
    
    def _get_serp_results(
        self, 
        search_query: SearchQuery,
        query_dir: Path
    ) -> List[Dict[str, Any]]:
        """
        Uses BrightData's SERP API to fetch search engine results for a given query.
        
        Args:
            search_query: SearchQuery object with query and parameters
            query_dir: Directory to save results to
            
        Returns:
            List of search results as dictionaries
        """
        # BrightData API endpoint
        url = "https://api.brightdata.com/request"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.serp_api_key}"
        }
        
        # Construct the Google search URL with parameters
        encoded_query = quote(search_query.query)
        search_url = f"http://www.google.com/search?q={encoded_query}"
        
        # Add additional search parameters if provided
        if search_query.location:
            search_url += f"&gl={quote(search_query.location)}"
        if search_query.language:
            search_url += f"&hl={quote(search_query.language)}"
        
        # Add any extra parameters from the search query
        for key, value in search_query.extra_params.items():
            search_url += f"&{key}={quote(str(value))}"
        
        payload = {
            "zone": self.config.serp_zone,
            "url": search_url,
            "format": search_query.format_type
        }
        
        try:
            logger.info(f"Making request to BrightData SERP API: {search_url}")
            response = requests.post(url, headers=headers, json=payload)
            
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Error response: {response.status_code} - {response.text}")
                response.raise_for_status()
            
            # Save raw response for debugging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_ext = "json" if search_query.format_type == "json" else "html"
            response_file = query_dir / f"serp_response_{timestamp}.{file_ext}"
            self._write_to_file(response.text, response_file)
            logger.debug(f"Saved SERP response to {response_file}")
            
            # Process response based on format
            if search_query.format_type == "json":
                # Return parsed JSON directly
                json_response = json.loads(response.text)
                
                # Extract results based on JSON structure
                if isinstance(json_response, dict) and "results" in json_response:
                    # If results are nested in a "results" field
                    return json_response.get("results", [])
                elif isinstance(json_response, list):
                    # If results are directly a list
                    return json_response
                else:
                    logger.warning("Unexpected JSON structure from SERP API")
                    return []
            else:
                # Process HTML with BeautifulSoup
                html_content = response.text
                soup = BeautifulSoup(html_content, 'html.parser')
                
                results = []
                search_results = soup.select('div.g')
                
                for result in search_results[:search_query.result_count]:
                    title_elem = result.select_one('h3')
                    link_elem = result.select_one('a')
                    snippet_elem = result.select_one('div.VwiC3b')
                    
                    if title_elem and link_elem and 'href' in link_elem.attrs:
                        title = title_elem.get_text()
                        link = link_elem['href']
                        if link.startswith('/url?q='):
                            link = link[7:].split('&')[0]  # Extract actual URL from Google's redirect URL
                        
                        snippet = snippet_elem.get_text() if snippet_elem else None
                        
                        results.append({
                            "title": title, 
                            "link": link,
                            "snippet": snippet
                        })
                        
                        if len(results) >= search_query.result_count:
                            break
                
                return results
        
        except requests.exceptions.RequestException as e:
            logger.error(f"SERP API request failed: {str(e)}")
            if response := getattr(e, 'response', None):
                logger.error(f"Status code: {response.status_code}")
                logger.error(f"Response body: {response.text}")
            raise Exception(f"BrightData SERP API request failed: {str(e)}")
    
    def _scrape_content(
        self,
        search_result: SearchResult,
        search_query: SearchQuery,
        query_dir: Path
    ) -> ScrapedContent:
        """
        Scrapes content from a search result URL.
        
        Args:
            search_result: SearchResult object
            search_query: SearchQuery object with query parameters
            query_dir: Directory to save results to
            
        Returns:
            ScrapedContent object with scraped content
        """
        scraped_content = ScrapedContent(
            title=search_result.title,
            url=search_result.link,
            position=search_result.position
        )
        
        try:
            logger.info(f"Scraping content from result {search_result.position}: {search_result.title}")
            
            # Get page content
            page_content = self._get_page_content(
                search_result.link,
                render_js=search_query.render_js,
                format_type=search_query.format_type,
                query_dir=query_dir
            )
            
            # Create sanitized filename
            safe_title = "".join(c if c.isalnum() else "_" for c in search_result.title[:50])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{search_result.position}_{safe_title}_{timestamp}"
            
            # Process based on format
            if search_query.format_type == "json":
                # For JSON format, store the raw response
                scraped_content.metadata["raw_json"] = page_content
                
                # Save to file
                json_file = query_dir / f"{file_name}.json"
                self._write_to_file(json.dumps(page_content, indent=2), json_file)
                scraped_content.metadata["json_file"] = str(json_file)
            else:
                # For HTML format, store content and convert to Markdown
                html_content = page_content
                scraped_content.html_content = html_content
                
                # Convert to Markdown
                markdown_text = self._convert_html_to_markdown(html_content)
                scraped_content.markdown_content = markdown_text
                
                # Save HTML and Markdown to files
                html_file = query_dir / f"{file_name}.html"
                self._write_to_file(html_content, html_file)
                scraped_content.metadata["html_file"] = str(html_file)
                
                md_file = query_dir / f"{file_name}.md"
                self._write_to_file(markdown_text, md_file)
                scraped_content.metadata["markdown_file"] = str(md_file)
            
            scraped_content.success = True
            return scraped_content
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing {search_result.link}: {error_msg}")
            
            # Set error information in the scraped content
            scraped_content.success = False
            scraped_content.error = error_msg
            
            return scraped_content
    
    def _get_page_content(
        self,
        url: str,
        render_js: bool = True,
        format_type: str = "raw",
        query_dir: Optional[Path] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Uses BrightData's Web Unlocker to retrieve content of a webpage.
        
        Args:
            url: The target webpage URL
            render_js: Whether to enable JavaScript rendering
            format_type: Response format - "raw" (HTML) or "json"
            query_dir: Directory to save results to
            
        Returns:
            HTML content as text or JSON response
        """
        # BrightData API endpoint
        api_url = "https://api.brightdata.com/request"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.unlocker_api_key}"
        }
        
        payload = {
            "zone": self.config.unlocker_zone,
            "url": url,
            "format": format_type
        }
        
        # Add optional js_rendering parameter
        if not render_js:
            payload["js_rendering"] = "disabled"
        
        try:
            logger.info(f"Making request to BrightData Web Unlocker API: {url}")
            response = requests.post(api_url, headers=headers, json=payload)
            
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Error response: {response.status_code} - {response.text}")
                response.raise_for_status()
            
            # Determine where to save the response
            save_dir = query_dir if query_dir else self.config.results_dir
            
            # Save raw response for debugging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_ext = "json" if format_type == "json" else "html"
            response_file = save_dir / f"unlocker_response_{timestamp}.{file_ext}"
            self._write_to_file(response.text, response_file)
            logger.debug(f"Saved Unlocker response to {response_file}")
            
            # Process based on format
            if format_type == "json":
                return json.loads(response.text)
            else:
                return response.text
                
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            logger.error(f"Web Unlocker API request failed for {url}: {error_msg}")
            
            # Log the failed URL to the exceptions file
            self._append_to_exceptions_file(url, error_msg)
            
            if response := getattr(e, 'response', None):
                logger.error(f"Status code: {response.status_code}")
                logger.error(f"Response body: {response.text}")
            raise Exception(f"BrightData Web Unlocker API request failed: {error_msg}")

    def get_page_content(
        self, 
        url: str, 
        render_js: bool = True, 
        format_type: str = "raw"
    ) -> Union[Dict[str, Any], Tuple[str, str]]:
        """
        Public method to retrieve content from a single URL without performing a search.
        
        Args:
            url: The target webpage URL
            render_js: Whether to enable JavaScript rendering
            format_type: Response format - "raw" (HTML) or "json"
            
        Returns:
            If format_type is "json": Dict with JSON response
            If format_type is "raw": Tuple of (HTML content, Markdown content)
            
        Raises:
            Exception: If content retrieval fails and recovery attempts are unsuccessful
        """
        if not url or not url.strip():
            logger.error("Empty URL provided to get_page_content")
            raise ValueError("URL cannot be empty")
            
        if not url.startswith(('http://', 'https://')):
            logger.error(f"Invalid URL format: {url}")
            raise ValueError("URL must start with http:// or https://")
            
        try:
            # Get page content
            try:
                content = self._get_page_content(
                    url,
                    render_js=render_js,
                    format_type=format_type
                )
            except Exception as content_error:
                logger.error(f"Error in _get_page_content for {url}: {str(content_error)}")
                
                # Special handling for specific errors
                if "403" in str(content_error):
                    logger.warning("Received 403 Forbidden, retrying with JavaScript disabled")
                    if render_js:
                        # Try again with JavaScript disabled
                        content = self._get_page_content(
                            url,
                            render_js=False,
                            format_type=format_type
                        )
                    else:
                        raise  # Already tried with JS disabled
                else:
                    raise  # Re-raise the original error
            
            # Process based on format
            if format_type == "json":
                return content
            else:
                html_content = content
                try:
                    markdown_content = self._convert_html_to_markdown(html_content)
                    
                    # Check if we got meaningful content
                    if not markdown_content or not markdown_content.strip():
                        logger.warning(f"Empty markdown content from {url}, returning placeholder")
                        markdown_content = f"# Content from {url}\n\nThe content could not be properly converted to Markdown.\n\nPlease check the URL or try again later."
                    
                    return html_content, markdown_content
                    
                except Exception as md_error:
                    logger.error(f"Error converting HTML to Markdown for {url}: {str(md_error)}")
                    
                    # Create minimal fallback content
                    fallback_markdown = f"# Content from {url}\n\n"
                    
                    # Try to extract basic text
                    try:
                        soup = BeautifulSoup(html_content, 'html.parser')
                        text_content = soup.get_text(separator="\n\n")
                        fallback_markdown += text_content
                    except Exception:
                        fallback_markdown += "Error extracting content from the page."
                    
                    return html_content, fallback_markdown
                
        except Exception as e:
            logger.error(f"Error retrieving content from {url}: {str(e)}")
            
            # Create error response with enough context for the caller
            error_html = f"<html><body><h1>Error retrieving content</h1><p>{str(e)}</p></body></html>"
            error_markdown = f"# Error Retrieving Content\n\nThere was an error retrieving content from {url}:\n\n```\n{str(e)}\n```\n\nPlease try again or try a different URL."
            
            # Decide whether to raise or return error content
            if format_type == "json":
                raise  # JSON format doesn't have a good way to return error content
            else:
                logger.warning(f"Returning error content for {url}")
                return error_html, error_markdown


if __name__ == "__main__":
    """
    Command-line interface to test BrightDataSearcher functionality.
    
    Usage:
        python brightdata_search.py --search "your search query"
        python brightdata_search.py --url "https://example.com"
        
    Environment variables (required if not passed as arguments):
        BRIGHT_DATA_SERP_API_KEY
        BRIGHT_DATA_UNLOCKER_API_KEY
        BRIGHT_DATA_SERP_ZONE
        BRIGHT_DATA_UNLOCKER_ZONE
    """
    import argparse
    import os
    from datetime import datetime
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Test BrightData search and content retrieval")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", type=str, help="Search query to execute")
    group.add_argument("--url", type=str, help="URL to retrieve content from")
    
    # Configuration arguments
    parser.add_argument("--serp-api-key", type=str, help="BrightData SERP API key")
    parser.add_argument("--unlocker-api-key", type=str, help="BrightData Web Unlocker API key")
    parser.add_argument("--serp-zone", type=str, help="BrightData SERP zone")
    parser.add_argument("--unlocker-zone", type=str, help="BrightData Web Unlocker zone")
    parser.add_argument("--results-dir", type=str, default="results", help="Directory to store results")
    parser.add_argument("--result-count", type=int, default=5, help="Number of search results to retrieve")
    parser.add_argument("--location", type=str, default="US", help="Location for search results")
    parser.add_argument("--language", type=str, default="en", help="Language for search results")
    
    args = parser.parse_args()
    
    # Get API keys from arguments or environment variables
    serp_api_key = args.serp_api_key or os.environ.get("BRIGHT_DATA_SERP_API_KEY")
    unlocker_api_key = args.unlocker_api_key or os.environ.get("BRIGHT_DATA_UNLOCKER_API_KEY")
    serp_zone = args.serp_zone or os.environ.get("BRIGHT_DATA_SERP_ZONE")
    unlocker_zone = args.unlocker_zone or os.environ.get("BRIGHT_DATA_UNLOCKER_ZONE")
    
    # Validate required parameters
    if not all([serp_api_key, unlocker_api_key, serp_zone, unlocker_zone]):
        missing = []
        if not serp_api_key: missing.append("SERP API key")
        if not unlocker_api_key: missing.append("Unlocker API key")
        if not serp_zone: missing.append("SERP zone")
        if not unlocker_zone: missing.append("Unlocker zone")
        
        parser.error(f"Missing required configuration: {', '.join(missing)}. "
                    f"Provide them as arguments or environment variables.")
    
    # Create results directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(args.results_dir) / f"test_{timestamp}"
    results_dir.mkdir(exist_ok=True, parents=True)
    
    # Create configuration
    config = BrightDataConfig(
        serp_api_key=serp_api_key,
        unlocker_api_key=unlocker_api_key,
        serp_zone=serp_zone,
        unlocker_zone=unlocker_zone,
        results_dir=results_dir
    )
    
    # Initialize searcher
    searcher = BrightDataSearcher(
        config=config,
        log_level=logging.INFO,
        log_to_file=True,
        log_file=str(results_dir / "brightdata_search.log")
    )
    
    if args.search:
        # Perform a search
        print(f"\n=== Performing search for: {args.search} ===\n")
        
        query = SearchQuery(
            query=args.search,
            result_count=args.result_count,
            location=args.location,
            language=args.language,
            render_js=True,
            format_type="raw"
        )
        
        response = searcher.search(query, scrape_content=True)
        
        # Print search results
        print("\nSearch Results:")
        for idx, result in enumerate(response.search_results, start=1):
            print(f"{idx}. {result.title}")
            print(f"   URL: {result.link}")
            print(f"   Snippet: {result.snippet}")
            print()
        
        # Print scraped content summary
        print("\nScraped Content Summary:")
        print(f"Total scraped: {len(response.scraped_contents)}")
        print(f"Successful: {sum(1 for c in response.scraped_contents if c.success)}")
        print(f"Failed: {sum(1 for c in response.scraped_contents if not c.success)}")
        
        # Save summary
        summary_file = results_dir / "search_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(response.to_dict(), f, indent=2)
        
        print(f"\nResults saved to: {results_dir}")
        print(f"Summary saved to: {summary_file}")
    
    elif args.url:
        # Retrieve content from URL
        print(f"\n=== Retrieving content from: {args.url} ===\n")
        
        try:
            html_content, markdown_content = searcher.get_page_content(
                url=args.url,
                render_js=True,
                format_type="raw"
            )
            
            # Save content to files
            html_file = results_dir / "content.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            md_file = results_dir / "content.md"
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            print(f"HTML content saved to: {html_file}")
            print(f"Markdown content saved to: {md_file}")
            
            # Print snippet of Markdown
            print("\nFirst 500 characters of Markdown content:")
            print("-" * 80)
            print(markdown_content[:500])
            print("-" * 80)
            
            print(f"\nResults saved to: {results_dir}")
            
        except Exception as e:
            print(f"Error retrieving content: {str(e)}") 