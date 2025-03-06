import os
import logging
from typing import Optional, List, Dict, Any, BinaryIO, Union
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from webserver.config import settings

logger = logging.getLogger(__name__)

class S3Storage:
    
    """
    A storage class for handling documents in S3 or MinIO.
    Supports both AWS S3 and local MinIO environments using the same interface.
    """
    
    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        use_ssl: bool = True,
        create_bucket_if_not_exists: bool = True
    ):
        """
        Initialize the S3 storage client.
        
        Args:
            bucket_name: Name of the S3 bucket to use
            aws_access_key_id: AWS access key or MinIO access key
            aws_secret_access_key: AWS secret key or MinIO secret key
            endpoint_url: Custom endpoint URL for MinIO (None for AWS S3)
            region_name: AWS region name
            use_ssl: Whether to use SSL for connections
            create_bucket_if_not_exists: Attempt to create the bucket if it doesn't exist
        """
        self.bucket_name = bucket_name
        
        # Use environment variables if credentials not provided
        self.aws_access_key_id = aws_access_key_id or os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = aws_secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.region_name = region_name or os.environ.get('AWS_REGION', 'us-east-1')
        self.endpoint_url = endpoint_url or os.environ.get('S3_ENDPOINT_URL')
        self.use_ssl = use_ssl
        
        # Determine if we're using MinIO or AWS S3
        self.is_minio = self.endpoint_url is not None
        self._initialize_client()
        
        if create_bucket_if_not_exists:
            self._ensure_bucket_exists()
    
    def _initialize_client(self):
        """Initialize the S3 client using boto3."""
        session_kwargs = {
            'aws_access_key_id': self.aws_access_key_id,
            'aws_secret_access_key': self.aws_secret_access_key,
            'region_name': self.region_name,
        }
        
        # Filter out None values
        session_kwargs = {k: v for k, v in session_kwargs.items() if v is not None}
        
        session = boto3.session.Session(**session_kwargs)
        
        client_kwargs = {}
        if self.endpoint_url:
            client_kwargs['endpoint_url'] = self.endpoint_url
            # For MinIO and other S3 compatible services
            client_kwargs['use_ssl'] = self.use_ssl
        
        self.s3_client = session.client('s3', **client_kwargs)
        self.s3_resource = session.resource('s3', **client_kwargs)
        self.bucket = self.s3_resource.Bucket(self.bucket_name)
    
    def _ensure_bucket_exists(self):
        """Create the bucket if it doesn't exist."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} exists")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                logger.info(f"Bucket {self.bucket_name} does not exist. Creating it...")
                if self.is_minio or not self.region_name or self.region_name == 'us-east-1':
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                else:
                    # For AWS S3 with specific region
                    self.s3_client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={
                            'LocationConstraint': self.region_name
                        }
                    )
                logger.info(f"Bucket {self.bucket_name} created")
            else:
                logger.error(f"Error checking bucket {self.bucket_name}: {e}")
                raise
    
    def upload_file(
        self, 
        file_path: str, 
        object_key: str,
        metadata: Optional[Dict[str, str]] = None,
        extra_args: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Upload a file to S3 storage.
        
        Args:
            file_path: Local path to the file
            object_key: S3 object key (path within the bucket)
            metadata: Optional metadata to store with the object
            extra_args: Optional extra arguments for S3 upload
            
        Returns:
            bool: True if upload was successful
        """
        try:
            args = extra_args or {}
            if metadata:
                args['Metadata'] = metadata
            
            self.s3_client.upload_file(
                Filename=file_path,
                Bucket=self.bucket_name,
                Key=object_key,
                ExtraArgs=args
            )
            logger.info(f"Successfully uploaded {file_path} to {self.bucket_name}/{object_key}")
            return True
        except ClientError as e:
            logger.error(f"Error uploading file {file_path} to {self.bucket_name}/{object_key}: {e}")
            return False
    
    def upload_fileobj(
        self, 
        fileobj: BinaryIO, 
        object_key: str,
        metadata: Optional[Dict[str, str]] = None,
        extra_args: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Upload a file-like object to S3 storage.
        
        Args:
            fileobj: File-like object
            object_key: S3 object key (path within the bucket)
            metadata: Optional metadata to store with the object
            extra_args: Optional extra arguments for S3 upload
            
        Returns:
            bool: True if upload was successful
        """
        try:
            args = extra_args or {}
            if metadata:
                args['Metadata'] = metadata
            
            self.s3_client.upload_fileobj(
                Fileobj=fileobj,
                Bucket=self.bucket_name,
                Key=object_key,
                ExtraArgs=args
            )
            logger.info(f"Successfully uploaded file object to {self.bucket_name}/{object_key}")
            return True
        except ClientError as e:
            logger.error(f"Error uploading file object to {self.bucket_name}/{object_key}: {e}")
            return False
    
    def download_file(self, object_key: str, file_path: str) -> bool:
        """
        Download a file from S3 storage.
        
        Args:
            object_key: S3 object key (path within the bucket)
            file_path: Local path to save the file
            
        Returns:
            bool: True if download was successful
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            self.s3_client.download_file(
                Bucket=self.bucket_name,
                Key=object_key,
                Filename=file_path
            )
            logger.info(f"Successfully downloaded {self.bucket_name}/{object_key} to {file_path}")
            return True
        except ClientError as e:
            logger.error(f"Error downloading file {self.bucket_name}/{object_key} to {file_path}: {e}")
            return False
    
    def download_fileobj(self, object_key: str, fileobj: BinaryIO) -> bool:
        """
        Download a file from S3 storage into a file-like object.
        
        Args:
            object_key: S3 object key (path within the bucket)
            fileobj: File-like object to write to
            
        Returns:
            bool: True if download was successful
        """
        try:
            self.s3_client.download_fileobj(
                Bucket=self.bucket_name,
                Key=object_key,
                Fileobj=fileobj
            )
            logger.info(f"Successfully downloaded {self.bucket_name}/{object_key} to file object")
            return True
        except ClientError as e:
            logger.error(f"Error downloading file {self.bucket_name}/{object_key} to file object: {e}")
            return False
    
    def delete_file(self, object_key: str) -> bool:
        """
        Delete a file from S3 storage.
        
        Args:
            object_key: S3 object key (path within the bucket)
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            logger.info(f"Successfully deleted {self.bucket_name}/{object_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file {self.bucket_name}/{object_key}: {e}")
            return False
    
    def delete_files(self, object_keys: List[str]) -> bool:
        """
        Delete multiple files from S3 storage.
        
        Args:
            object_keys: List of S3 object keys to delete
            
        Returns:
            bool: True if all deletions were successful
        """
        if not object_keys:
            return True
            
        try:
            objects = [{'Key': key} for key in object_keys]
            self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': objects}
            )
            logger.info(f"Successfully deleted {len(object_keys)} objects from {self.bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting files from {self.bucket_name}: {e}")
            return False
    
    def list_files(self, prefix: str = "", max_keys: int = 1000) -> List[Dict[str, Any]]:
        """
        List files in the S3 bucket with the given prefix.
        
        Args:
            prefix: S3 object key prefix to filter by
            max_keys: Maximum number of keys to return
            
        Returns:
            List of dictionaries with file information (Key, LastModified, Size, etc.)
        """
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            result = []
            
            for page in paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            ):
                if 'Contents' in page:
                    result.extend(page['Contents'])
            
            return result
        except ClientError as e:
            logger.error(f"Error listing files in {self.bucket_name} with prefix {prefix}: {e}")
            return []
    
    def get_file_metadata(self, object_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a file in S3 storage.
        
        Args:
            object_key: S3 object key (path within the bucket)
            
        Returns:
            Dictionary with file metadata or None if not found
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            return response
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"File {self.bucket_name}/{object_key} not found")
            else:
                logger.error(f"Error getting metadata for {self.bucket_name}/{object_key}: {e}")
            return None
    
    def file_exists(self, object_key: str) -> bool:
        """
        Check if a file exists in S3 storage.
        
        Args:
            object_key: S3 object key (path within the bucket)
            
        Returns:
            bool: True if file exists
        """
        return self.get_file_metadata(object_key) is not None
    
    def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for an S3 object.
        
        Args:
            object_key: S3 object key (path within the bucket)
            expires_in: Expiration time in seconds
            
        Returns:
            Presigned URL string or None if generation failed
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_key
                },
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL for {self.bucket_name}/{object_key}: {e}")
            return None


def create_s3_storage_from_config() -> S3Storage:
    """
    Create an S3Storage instance from settings in config.py.
    
    Settings used:
    - S3_ENDPOINT: Endpoint URL for S3 or MinIO
    - S3_ACCESS_KEY: Access key
    - S3_SECRET_KEY: Secret key
    - S3_BUCKET_NAME: (Optional) Bucket name, default is "sbaw_chat_files"
    
    Returns:
        S3Storage instance
    """
    # Determine if we're using MinIO or AWS S3 based on the endpoint
    endpoint_url = settings.S3_ENDPOINT
    
    # Default bucket name if not specified
    bucket_name = getattr(settings, "S3_BUCKET_NAME", "sbaw_chat_files")
    
    # Use SSL if the endpoint is https
    use_ssl = endpoint_url.startswith("https://") if endpoint_url else True
    
    # Extract region from endpoint if possible
    region_name = None
    if endpoint_url and "amazonaws.com" in endpoint_url:
        # Try to extract region from AWS endpoint
        parts = endpoint_url.split(".")
        if len(parts) >= 4:
            region_name = parts[1]
    
    return S3Storage(
        bucket_name=bucket_name,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        endpoint_url=endpoint_url,
        region_name=region_name,
        use_ssl=use_ssl,
        create_bucket_if_not_exists=True
    )

def create_s3_storage_from_env() -> S3Storage:
    """
    Create an S3Storage instance from environment variables.
    
    Environment variables used:
    - S3_BUCKET_NAME: Name of the S3 bucket (required)
    - AWS_ACCESS_KEY_ID: AWS access key ID or MinIO access key
    - AWS_SECRET_ACCESS_KEY: AWS secret access key or MinIO secret key
    - S3_ENDPOINT_URL: Custom endpoint URL for MinIO (None for AWS S3)
    - AWS_REGION: AWS region name
    - S3_USE_SSL: Whether to use SSL (default: True)
    
    Returns:
        S3Storage instance
    """
    # For backward compatibility, try environment variables first
    bucket_name = os.environ.get('S3_BUCKET_NAME')
    if not bucket_name:
        # If not found in environment, use settings or default
        bucket_name = getattr(settings, "S3_BUCKET_NAME", "sbaw_chat_files")
    
    # Get endpoint URL from environment or settings
    endpoint_url = os.environ.get('S3_ENDPOINT_URL') or settings.S3_ENDPOINT
    
    # Use SSL based on environment or endpoint URL
    use_ssl = os.environ.get('S3_USE_SSL', 'true').lower() != 'false'
    if endpoint_url and not os.environ.get('S3_USE_SSL'):
        use_ssl = endpoint_url.startswith("https://")
    
    # Get credentials from environment or settings
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID') or settings.S3_ACCESS_KEY
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY') or settings.S3_SECRET_KEY
    
    # Get region from environment
    region_name = os.environ.get('AWS_REGION')
    
    return S3Storage(
        bucket_name=bucket_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        endpoint_url=endpoint_url,
        region_name=region_name,
        use_ssl=use_ssl,
        create_bucket_if_not_exists=True
    )

def create_chat_s3_storage() -> S3Storage:
    """
    Create an S3Storage instance specifically for chat file storage.
    Uses the 'sbaw_chat_files' bucket and inherits other settings from config.
    
    Returns:
        S3Storage: Instance configured for chat file storage
    """
    # Prefer the config-based method
    s3 = create_s3_storage_from_config()
    
    # Override bucket name for chat files
    if s3.bucket_name != "sbaw_chat_files":
        s3 = S3Storage(
            bucket_name="sbaw_chat_files",
            # Inherit other settings
            endpoint_url=s3.endpoint_url,
            aws_access_key_id=s3.aws_access_key_id,
            aws_secret_access_key=s3.aws_secret_access_key,
            region_name=s3.region_name,
            use_ssl=s3.use_ssl,
            create_bucket_if_not_exists=True
        )
    
    return s3

def get_chat_file_path(chat_id: str, file_id: str, filename: str) -> str:
    """
    Create a standardized S3 object key for chat files.
    
    Args:
        chat_id: ID of the chat
        file_id: ID of the file 
        filename: Original filename
        
    Returns:
        str: S3 object key path
    """
    return f"{chat_id}/{file_id}/{filename}"
