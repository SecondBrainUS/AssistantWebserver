"""
File conversion utilities for processing different file types into text for LLM consumption.
"""
import logging
import os
import io
import json
import tempfile
import csv
import pandas as pd
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from markitdown import MarkItDown
from webserver.util.s3 import create_chat_s3_storage, get_chat_file_path
from webserver.db.chatdb.db import mongodb_client

logger = logging.getLogger(__name__)


async def process_files_for_llm(chat_id: str, file_ids: List[str], notify_callback=None) -> Dict[str, Dict[str, Any]]:
    """
    Process a list of file IDs attached to a chat for LLM consumption.
    Downloads the files from S3 and converts them to text format with appropriate markdown formatting.
    
    Args:
        chat_id: The ID of the chat
        file_ids: List of file IDs to process
        notify_callback: Optional async callback function to notify clients about file processing.
                        Should accept parameters: filename, message
        
    Returns:
        Dictionary mapping file IDs to dictionaries containing:
        - filename: Original filename
        - content_type: MIME type of the file
        - text_content: Converted text content
    """
    if not file_ids:
        return {}
        
    # Initialize S3 storage for chat files
    s3_storage = create_chat_s3_storage()
    
    # Get chat document from MongoDB to obtain file metadata
    try:
        chat = await mongodb_client.db["chats"].find_one({"chat_id": chat_id})
        if not chat:
            logger.error(f"Chat {chat_id} not found in database")
            return {}
            
        # Extract file metadata from chat document
        chat_files = chat.get("files", [])
        if not chat_files:
            logger.warning(f"No files found in chat {chat_id}")
            return {}
    except Exception as e:
        logger.error(f"Error retrieving chat document: {str(e)}", exc_info=True)
        return {}
        
    # Build result dictionary mapping file IDs to their converted content
    file_contents = {}
    
    for file_id in file_ids:
        # Find file metadata in chat document
        file_metadata = next((f for f in chat_files if f.get("fileid") == file_id), None)
        
        if not file_metadata:
            logger.warning(f"File {file_id} not found in chat {chat_id}")
            continue
            
        # Get filename for notifications and file output
        filename = file_metadata.get("filename", "unknown")
        
        # Notify clients that we're processing this file if callback provided
        if notify_callback:
            try:
                await notify_callback(
                    filename=filename,
                    message=f"Converting file '{filename}' for AI processing"
                )
            except Exception as notify_error:
                logger.warning(f"Error in notification callback: {str(notify_error)}")
            
        # Get file from S3
        try:
            # Create a BytesIO object to hold the file content
            file_content = io.BytesIO()
            
            # Get the object key from file metadata or construct it
            object_key = file_metadata.get("object_key")
            if not object_key:
                object_key = get_chat_file_path(chat_id, file_id, file_metadata.get('filename'))
            
            # Download the file from S3
            success = s3_storage.download_fileobj(
                object_key=object_key,
                fileobj=file_content
            )
            
            if not success:
                logger.error(f"Failed to download file {file_id} from S3")
                continue
            
            # Reset file pointer to beginning of file
            file_content.seek(0)
            
            # Convert file to text based on content type
            content_type = file_metadata.get("content_type", "")
            converted_text = convert_file_for_llm(
                file_content=file_content,
                file_metadata=file_metadata
            )
            
            if converted_text:
                # Store the converted text in the result dictionary
                file_contents[file_id] = {
                    "filename": filename,
                    "content_type": content_type,
                    "text_content": converted_text
                }
            
        except Exception as e:
            logger.error(f"Error processing file {file_id}: {str(e)}", exc_info=True)
            continue
            
    # Return the mapping of file IDs to their converted content
    return file_contents


def convert_file_for_llm(file_content: io.BytesIO, file_metadata: Dict[str, Any]) -> str:
    """
    Convert a file to text for LLM processing based on its content type.
    
    Args:
        file_content: BytesIO object containing the file data
        file_metadata: Dictionary of file metadata including content_type and filename
        
    Returns:
        Converted text content
    """
    content_type = file_metadata.get("content_type", "")
    filename = file_metadata.get("filename", "")
    
    logger.info(f"Converting file {filename} with content type {content_type}")
    
    # Map content types to converter functions
    content_type_mapping = {
        "text/csv": convert_csv_to_text,
        "application/csv": convert_csv_to_text,
        "application/pdf": convert_pdf_to_text,
        "text/plain": convert_text_to_text,
        "text/markdown": convert_text_to_text,
        "application/json": convert_text_to_text,
        "text/html": convert_html_to_text,
        "application/xml": convert_text_to_text
    }
    
    # Use filename extension as a fallback if content_type is not recognized
    ext_mapping = {
        ".csv": convert_csv_to_text,
        ".pdf": convert_pdf_to_text,
        ".txt": convert_text_to_text,
        ".md": convert_text_to_text,
        ".json": convert_text_to_text,
        ".html": convert_html_to_text,
        ".htm": convert_html_to_text,
        ".xml": convert_text_to_text
    }
    
    # Determine converter function
    converter_func = None
    
    # Try by content type first
    for ct, func in content_type_mapping.items():
        if content_type.lower().startswith(ct.lower()):
            converter_func = func
            break
            
    # If no converter found by content type, try by file extension
    if not converter_func:
        _, ext = os.path.splitext(filename.lower())
        converter_func = ext_mapping.get(ext)
        
    # Default to plain text if no converter found
    if not converter_func:
        logger.warning(f"No specific converter found for {content_type}, using default text converter")
        converter_func = convert_text_to_text
        
    # Convert the file
    try:
        return converter_func(file_content, file_metadata)
    except Exception as e:
        logger.error(f"Error converting file {filename}: {str(e)}", exc_info=True)
        return f"Error converting file: {str(e)}"


def convert_csv_to_text(file_content: io.BytesIO, file_metadata: Dict[str, Any]) -> str:
    """
    Convert CSV file to human-readable text format.
    
    Args:
        file_content: BytesIO object containing the CSV data
        file_metadata: Dictionary of file metadata
        
    Returns:
        Formatted text representation of the CSV
    """
    try:
        # Read CSV into a pandas DataFrame for easier handling
        df = pd.read_csv(file_content)
        
        # If the dataframe is too large, truncate it
        max_rows = 500
        max_cols = 20
        
        if len(df) > max_rows:
            logger.info(f"Truncating CSV with {len(df)} rows to {max_rows} rows")
            df = pd.concat([df.head(max_rows // 2), df.tail(max_rows // 2)])
            truncated_note = f"\n\n*Note: This CSV file has been truncated. Original file has {len(df)} rows.*\n\n"
        else:
            truncated_note = ""
            
        if len(df.columns) > max_cols:
            logger.info(f"Truncating CSV with {len(df.columns)} columns to {max_cols} columns")
            df = df.iloc[:, :max_cols]
            truncated_note += f"\n\n*Note: This CSV file has been truncated. Only showing first {max_cols} columns.*\n\n"
        
        # Format as markdown table with headers
        markdown_table = df.to_markdown(index=False)
        
        # Add file info
        result = f"```csv\n{markdown_table}\n```{truncated_note}"
        return result
        
    except Exception as e:
        logger.error(f"Error converting CSV: {str(e)}", exc_info=True)
        
        # Fallback to basic CSV display if pandas conversion fails
        try:
            file_content.seek(0)  # Reset file pointer
            reader = csv.reader(io.TextIOWrapper(file_content, encoding='utf-8'))
            
            # Get headers and first few rows
            rows = []
            for i, row in enumerate(reader):
                rows.append(row)
                if i >= 100:  # Limit to 100 rows
                    break
                    
            if not rows:
                return "Empty CSV file"
                
            # Format as plain text
            result = "```csv\n"
            for row in rows:
                result += ",".join(row) + "\n"
            result += "```"
            
            return result
        except Exception as fallback_error:
            logger.error(f"Fallback CSV conversion failed: {str(fallback_error)}", exc_info=True)
            return f"Failed to parse CSV file: {str(e)}"


def convert_pdf_to_text(file_content: io.BytesIO, file_metadata: Dict[str, Any]) -> str:
    """
    Convert PDF file to text using MarkItDown.
    
    Args:
        file_content: BytesIO object containing the PDF data
        file_metadata: Dictionary of file metadata
        
    Returns:
        Extracted text from the PDF
    """
    # Write PDF to a temporary file because MarkItDown needs a file path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(file_content.read())
        tmp_filepath = tmp_file.name
        
    try:
        # Use MarkItDown to convert PDF to markdown text
        md = MarkItDown()
        result = md.convert(tmp_filepath)
        markdown_text = result.text_content
        
        # If conversion result is empty, try a fallback message
        if not markdown_text or not markdown_text.strip():
            return "PDF content could not be extracted. The file might be scanned or contain only images."
            
        return markdown_text
        
    except Exception as e:
        logger.error(f"Error converting PDF: {str(e)}", exc_info=True)
        return f"Failed to extract text from PDF: {str(e)}"
        
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_filepath):
            try:
                os.remove(tmp_filepath)
            except Exception as cleanup_error:
                logger.warning(f"Failed to remove temporary file: {str(cleanup_error)}")


def convert_text_to_text(file_content: io.BytesIO, file_metadata: Dict[str, Any]) -> str:
    """
    Convert text files (txt, md, json) to text format.
    
    Args:
        file_content: BytesIO object containing the text data
        file_metadata: Dictionary of file metadata
        
    Returns:
        Text content with appropriate formatting
    """
    try:
        # Read the text content
        text_content = file_content.read().decode('utf-8')
        
        # Get file extension
        filename = file_metadata.get("filename", "")
        _, ext = os.path.splitext(filename.lower())
        
        # Format based on file type
        if ext == ".json":
            # Try to pretty-print JSON
            try:
                parsed_json = json.loads(text_content)
                text_content = json.dumps(parsed_json, indent=2)
                return f"```json\n{text_content}\n```"
            except json.JSONDecodeError:
                return f"```\n{text_content}\n```"
        elif ext == ".md":
            # Markdown files can be returned as is
            return text_content
        else:
            # Plain text files
            return f"```\n{text_content}\n```"
            
    except UnicodeDecodeError:
        # If not UTF-8, try with Latin-1 encoding
        try:
            file_content.seek(0)
            text_content = file_content.read().decode('latin-1')
            return f"```\n{text_content}\n```"
        except Exception as fallback_error:
            logger.error(f"Error decoding text with fallback encoding: {str(fallback_error)}", exc_info=True)
            return "File contains binary or non-text content that cannot be displayed."
    except Exception as e:
        logger.error(f"Error converting text file: {str(e)}", exc_info=True)
        return f"Failed to read text file: {str(e)}"


def convert_html_to_text(file_content: io.BytesIO, file_metadata: Dict[str, Any]) -> str:
    """
    Convert HTML file to markdown text using MarkItDown.
    
    Args:
        file_content: BytesIO object containing the HTML data
        file_metadata: Dictionary of file metadata
        
    Returns:
        Markdown representation of the HTML content
    """
    try:
        # Read the HTML content
        html_content = file_content.read().decode('utf-8')
        
        # Write to temporary file for MarkItDown
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".html", encoding="utf-8") as tmp_file:
            tmp_file.write(html_content)
            tmp_filepath = tmp_file.name
            
        try:
            # Convert HTML to Markdown
            md = MarkItDown()
            result = md.convert(tmp_filepath)
            markdown_text = result.text_content
            
            # If conversion result is empty, try a fallback with BeautifulSoup
            if not markdown_text or not markdown_text.strip():
                soup = BeautifulSoup(html_content, 'html.parser')
                markdown_text = soup.get_text(separator="\n\n")
                markdown_text = f"# HTML Content\n\n{markdown_text}"
                
            return markdown_text
            
        except Exception as conversion_error:
            logger.error(f"Error in MarkItDown conversion: {str(conversion_error)}", exc_info=True)
            
            # Fallback to BeautifulSoup for basic text extraction
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text(separator="\n\n")
            return f"# HTML Content\n\n{text_content}"
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_filepath):
                try:
                    os.remove(tmp_filepath)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to remove temporary file: {str(cleanup_error)}")
                    
    except Exception as e:
        logger.error(f"Error converting HTML file: {str(e)}", exc_info=True)
        return f"Failed to convert HTML: {str(e)}" 