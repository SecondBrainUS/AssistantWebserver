# S3 Storage Module

This module provides a unified interface for document storage using either AWS S3 or a local MinIO container. It offers a simple and consistent way to interact with S3-compatible storage systems.

## Features

- Seamless support for both AWS S3 and MinIO
- Configuration through config.py, constructor parameters, or environment variables
- Automatic bucket creation if needed
- Full support for document operations:
  - Upload files from local path or memory
  - Download files to local path or memory
  - List files with prefix filtering
  - Delete single or multiple files
  - Check file existence
  - Get file metadata
  - Generate presigned URLs for temporary access

## Installation Requirements

The module requires the `boto3` package, which is the official AWS SDK for Python:

```bash
pip install boto3
```

## Usage Examples

### Using Configuration from config.py

```python
from webserver.util.s3 import create_s3_storage_from_config

# Initialize using settings from config.py
s3 = create_s3_storage_from_config()

# Upload a file
s3.upload_file(
    file_path="local_file.txt",
    object_key="documents/file.txt",
    metadata={"author": "User", "description": "Document"}
)
```

### Using with AWS S3

```python
from webserver.util.s3 import S3Storage

# Initialize with AWS S3
s3 = S3Storage(
    bucket_name="my-documents-bucket",
    aws_access_key_id="YOUR_AWS_ACCESS_KEY",
    aws_secret_access_key="YOUR_AWS_SECRET_KEY",
    region_name="us-east-1"
)

# Upload a file
s3.upload_file(
    file_path="local_file.txt",
    object_key="documents/file.txt",
    metadata={"author": "User", "description": "Document"}
)

# Download a file
s3.download_file(
    object_key="documents/file.txt", 
    file_path="downloaded_file.txt"
)
```

### Using with MinIO

```python
from webserver.util.s3 import S3Storage

# Initialize with MinIO
s3 = S3Storage(
    bucket_name="my-documents-bucket",
    aws_access_key_id="minioadmin",  # Default MinIO credentials
    aws_secret_access_key="minioadmin",
    endpoint_url="http://localhost:9000",  # MinIO server URL
    use_ssl=False  # Set to True if MinIO is configured with SSL
)

# Operations are the same as with AWS S3
```

### Using Environment Variables

Set environment variables:

```bash
# Common configuration
export S3_BUCKET_NAME=my-documents-bucket

# For AWS S3
export AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_KEY
export AWS_REGION=us-east-1

# For MinIO (overrides AWS S3 if both are set)
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export S3_ENDPOINT_URL=http://localhost:9000
export S3_USE_SSL=false
```

Then in your code:

```python
from webserver.util.s3 import create_s3_storage_from_env

# Create from environment variables
s3 = create_s3_storage_from_env()

# Use normally
s3.upload_file("local_file.txt", "documents/file.txt")
```

### Specifically for Chat Files

For the chat system's file storage, use the dedicated function:

```python
from webserver.util.s3 import create_chat_s3_storage

# Create S3 storage specifically for chat files
# This uses the sbaw-chat-files bucket
s3 = create_chat_s3_storage()

# Use for chat file operations
s3.upload_file("local_file.txt", f"{chat_id}/{file_id}/document.txt")
```

## Running MinIO Locally

The repository includes a Docker Compose file to run MinIO locally for development and testing:

```bash
cd AssistantWebserver
docker-compose -f docker-compose-minio.yml up -d
```

This starts a MinIO server available at:
- API Endpoint: http://localhost:9000
- Web Console: http://localhost:9001 (login with minioadmin/minioadmin)

## Configuration Priority

The module uses the following priority for configuration:

1. Explicitly provided parameters in constructor
2. Environment variables
3. Settings from config.py
4. Default values

## API Reference

See the docstrings in the `s3.py` file for detailed API documentation. The main class is `S3Storage` which provides methods for all common S3 operations.

## Settings in config.py

The module recognizes the following settings from config.py:

| Setting | Description | Default |
|---------|-------------|---------|
| S3_ENDPOINT | Endpoint URL for S3 or MinIO | None |
| S3_ACCESS_KEY | Access key ID | None |
| S3_SECRET_KEY | Secret key | None |
| S3_BUCKET_NAME | Name of the S3 bucket | "sbaw-chat-files" |

## Environment Variables

The module recognizes the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| S3_BUCKET_NAME | Name of the S3 bucket | From config |
| AWS_ACCESS_KEY_ID | AWS/MinIO access key ID | From config |
| AWS_SECRET_ACCESS_KEY | AWS/MinIO secret access key | From config |
| S3_ENDPOINT_URL | Custom endpoint URL for MinIO | From config |
| AWS_REGION | AWS region name | Determined from endpoint |
| S3_USE_SSL | Whether to use SSL for connections | true |

## Error Handling

All methods return appropriate values to indicate success or failure (usually `True`/`False` or the requested data/`None`). Errors are logged using the Python logging system.

## Switching Between AWS S3 and MinIO

The key to switching between AWS S3 and MinIO is the `endpoint_url` parameter:

- When `endpoint_url` is `None` (default), the module uses AWS S3
- When `endpoint_url` is set (e.g., to "http://localhost:9000"), the module uses that endpoint as an S3-compatible service like MinIO

This makes it easy to use MinIO for local development and testing, and AWS S3 for production, without changing your code. 