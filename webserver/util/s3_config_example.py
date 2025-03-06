#!/usr/bin/env python3
"""
Example showing how to use the S3 storage module with configuration from config.py.
"""

import os
import io
import tempfile
from webserver.config import settings
from webserver.util.s3 import (
    S3Storage,
    create_s3_storage_from_env,
    create_s3_storage_from_config,
    create_chat_s3_storage
)

def using_config_example():
    """Example using settings from config.py."""
    print("===== Using Config Settings Example =====")
    
    # Create an S3Storage instance using config settings
    s3 = create_s3_storage_from_config()
    
    print(f"S3 Storage initialized with:")
    print(f"  - Bucket: {s3.bucket_name}")
    print(f"  - Endpoint: {s3.endpoint_url}")
    print(f"  - Region: {s3.region_name}")
    print(f"  - Using SSL: {s3.use_ssl}")
    
    # Use the S3 storage for file operations
    perform_example_operations(s3)

def chat_files_example():
    """Example specifically for chat files."""
    print("===== Chat Files Example =====")
    
    # Create an S3Storage instance for chat files
    # This will use the sbaw-chat-files bucket
    s3 = create_chat_s3_storage()
    
    print(f"Chat S3 Storage initialized with:")
    print(f"  - Bucket: {s3.bucket_name}")
    print(f"  - Endpoint: {s3.endpoint_url}")
    
    # Upload a file within a chat's folder structure
    chat_id = "example-chat-123"
    file_id = "example-file-456"
    
    # Example operations for chat files
    perform_chat_file_operations(s3, chat_id, file_id)

def perform_example_operations(s3):
    """Perform common S3 operations as an example."""
    # File to upload
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
        f.write("This is test content for the S3 config example.")
        temp_file_path = f.name
    
    try:
        # Upload a file
        print("Uploading file...")
        object_key = "test-files/config-example.txt"
        
        success = s3.upload_file(
            file_path=temp_file_path,
            object_key=object_key,
            metadata={"description": "Config example file"}
        )
        print(f"Upload success: {success}")
        
        # List files
        print("Listing files:")
        files = s3.list_files(prefix="test-files/")
        for file in files:
            print(f"  - {file['Key']}, Size: {file['Size']} bytes")
        
        # Get file metadata
        metadata = s3.get_file_metadata(object_key)
        if metadata:
            print("File metadata:")
            print(f"  - Content Type: {metadata.get('ContentType')}")
            print(f"  - Last Modified: {metadata.get('LastModified')}")
            print(f"  - Custom Metadata: {metadata.get('Metadata')}")
        
        # Delete the test file
        print("Cleaning up test file...")
        s3.delete_file(object_key)
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

def perform_chat_file_operations(s3, chat_id, file_id):
    """Perform chat-specific file operations."""
    # File to upload
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
        f.write("This is a chat attachment example.")
        temp_file_path = f.name
    
    try:
        # Upload a file to chat directory structure
        print(f"Uploading file to chat {chat_id}...")
        filename = "attachment.txt"
        object_key = f"{chat_id}/{file_id}/{filename}"
        
        success = s3.upload_file(
            file_path=temp_file_path,
            object_key=object_key,
            metadata={
                "chat_id": chat_id,
                "file_id": file_id,
                "description": "Chat attachment example"
            }
        )
        print(f"Upload success: {success}")
        
        # List files in this chat
        print(f"Listing files for chat {chat_id}:")
        files = s3.list_files(prefix=f"{chat_id}/")
        for file in files:
            print(f"  - {file['Key']}, Size: {file['Size']} bytes")
        
        # Delete the test file
        print("Cleaning up test file...")
        s3.delete_file(object_key)
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

if __name__ == "__main__":
    # Uncomment the example you want to run
    using_config_example()
    # chat_files_example() 