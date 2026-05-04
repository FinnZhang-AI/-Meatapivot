from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import logging
from typing import Optional, BinaryIO
import io

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        self.client: Optional[Minio] = None
        self.connected = False
    
    def connect(self):
        """Initialize MinIO connection"""
        try:
            self.client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            self.connected = True
            logger.info(f"Connected to MinIO at {settings.MINIO_ENDPOINT}")
        except Exception as e:
            logger.error(f"Failed to connect to MinIO: {e}")
            raise
    
    def create_bucket(self, bucket_name: str):
        """Create a bucket if it doesn't exist"""
        if not self.connected:
            raise RuntimeError("MinIO not connected")
        
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Bucket created: {bucket_name}")
            else:
                logger.debug(f"Bucket already exists: {bucket_name}")
        except S3Error as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            raise
    
    def upload_file(self, bucket_name: str, object_name: str, file_data: bytes, content_type: str = "application/octet-stream"):
        """Upload a file to MinIO"""
        if not self.connected:
            raise RuntimeError("MinIO not connected")
        
        try:
            self.client.put_object(
                bucket_name,
                object_name,
                io.BytesIO(file_data),
                len(file_data),
                content_type=content_type
            )
            logger.info(f"File uploaded: {bucket_name}/{object_name}")
            return f"{settings.MINIO_ENDPOINT}/{bucket_name}/{object_name}"
        except S3Error as e:
            logger.error(f"Failed to upload file: {e}")
            raise
    
    def download_file(self, bucket_name: str, object_name: str) -> bytes:
        """Download a file from MinIO"""
        if not self.connected:
            raise RuntimeError("MinIO not connected")
        
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"File downloaded: {bucket_name}/{object_name}")
            return data
        except S3Error as e:
            logger.error(f"Failed to download file: {e}")
            raise
    
    def delete_file(self, bucket_name: str, object_name: str):
        """Delete a file from MinIO"""
        if not self.connected:
            raise RuntimeError("MinIO not connected")
        
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"File deleted: {bucket_name}/{object_name}")
        except S3Error as e:
            logger.error(f"Failed to delete file: {e}")
            raise
    
    def list_files(self, bucket_name: str, prefix: str = "") -> list:
        """List files in a bucket"""
        if not self.connected:
            raise RuntimeError("MinIO not connected")
        
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            files = []
            for obj in objects:
                files.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None
                })
            return files
        except S3Error as e:
            logger.error(f"Failed to list files: {e}")
            raise
    
    def get_presigned_url(self, bucket_name: str, object_name: str, expires: int = 3600) -> str:
        """Get a presigned URL for file access"""
        if not self.connected:
            raise RuntimeError("MinIO not connected")
        
        try:
            from datetime import timedelta
            url = self.client.presigned_get_object(
                bucket_name,
                object_name,
                expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            logger.error(f"Failed to get presigned URL: {e}")
            raise


# Global storage service instance
storage_service = StorageService()