#!/usr/bin/env python3
"""
Example usages of the S3Storage module for both AWS S3 and MinIO.
"""

import os
import io
import tempfile
from .s3 import S3Storage

def aws_s3_example():
    """Example using AWS S3."""
    print("===== AWS S3 Example =====")
    
    # Configure S3 storage for AWS
    s3 = S3Storage(
        bucket_name="my-documents-bucket",
        # Credentials can also be provided via environment variables:
        # AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
        aws_access_key_id="YOUR_AWS_ACCESS_KEY",
        aws_secret_access_key="YOUR_AWS_SECRET_KEY",
        region_name="us-east-1",
        # No endpoint_url means AWS S3
    )
    
    # Example operations
    perform_example_operations(s3)


def minio_example():
    """Example using local MinIO."""
    print("===== MinIO Example =====")
    
    # Configure S3 storage for MinIO
    s3 = S3Storage(
        bucket_name="my-documents-bucket",
        aws_access_key_id="minioadmin",  # Default MinIO access key
        aws_secret_access_key="minioadmin",  # Default MinIO secret key
        endpoint_url="http://localhost:9000",  # MinIO server address
        # region_name not required for MinIO but can be specified
        use_ssl=False  # Set to True if MinIO is configured with SSL
    )
    
    # Example operations
    perform_example_operations(s3)


def environment_variables_example():
    """Example using environment variables for configuration."""
    print("===== Environment Variables Example =====")
    
    # Set environment variables (in a real application, these would be set outside the script)
    os.environ["S3_BUCKET_NAME"] = "my-documents-bucket"
    
    # For AWS S3:
    # os.environ["AWS_ACCESS_KEY_ID"] = "YOUR_AWS_ACCESS_KEY"
    # os.environ["AWS_SECRET_ACCESS_KEY"] = "YOUR_AWS_SECRET_KEY"
    # os.environ["AWS_REGION"] = "us-east-1"
    
    # For MinIO:
    os.environ["AWS_ACCESS_KEY_ID"] = "minioadmin"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "minioadmin"
    os.environ["S3_ENDPOINT_URL"] = "http://localhost:9000"
    os.environ["S3_USE_SSL"] = "false"
    
    # Create storage from environment variables
    from .s3 import create_s3_storage_from_env
    s3 = create_s3_storage_from_env()
    
    # Example operations
    perform_example_operations(s3)


def perform_example_operations(s3):
    """Perform common S3 operations as an example."""
    # File to upload
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
        f.write("This is test content for the S3 example.")
        temp_file_path = f.name
    
    try:
        # Upload a file
        print("Uploading file...")
        object_key = "documents/test-file.txt"
        metadata = {"author": "Test User", "description": "Example file"}
        success = s3.upload_file(
            file_path=temp_file_path,
            object_key=object_key,
            metadata=metadata
        )
        print(f"Upload success: {success}")
        
        # Upload from memory (file-like object)
        print("Uploading from memory...")
        memory_object_key = "documents/memory-file.txt"
        file_data = io.BytesIO(b"This is content from memory")
        s3.upload_fileobj(
            fileobj=file_data,
            object_key=memory_object_key
        )
        
        # List files
        print("Listing files:")
        files = s3.list_files(prefix="documents/")
        for file in files:
            print(f"  - {file['Key']}, Size: {file['Size']} bytes")
        
        # Check if file exists
        exists = s3.file_exists(object_key)
        print(f"File exists: {exists}")
        
        # Get file metadata
        metadata = s3.get_file_metadata(object_key)
        if metadata:
            print("File metadata:")
            print(f"  - Content Type: {metadata.get('ContentType')}")
            print(f"  - Last Modified: {metadata.get('LastModified')}")
            print(f"  - Content Length: {metadata.get('ContentLength')}")
            print(f"  - Custom Metadata: {metadata.get('Metadata')}")
        
        # Generate a presigned URL
        url = s3.get_presigned_url(object_key, expires_in=3600)
        print(f"Presigned URL (valid for 1 hour): {url}")
        
        # Download the file
        download_path = os.path.join(tempfile.gettempdir(), "downloaded-test-file.txt")
        print(f"Downloading to {download_path}...")
        s3.download_file(object_key, download_path)
        
        # Read the downloaded content
        with open(download_path, "r") as f:
            content = f.read()
            print(f"Downloaded content: {content}")
        
        # Delete the files
        print("Deleting files...")
        s3.delete_files([object_key, memory_object_key])
        
        # Verify deletion
        exists = s3.file_exists(object_key)
        print(f"File still exists: {exists} (should be False)")
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        if os.path.exists(download_path):
            os.unlink(download_path)


if __name__ == "__main__":
    # Uncomment the example you want to run
    # aws_s3_example()
    # minio_example()
    environment_variables_example() 