from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import List, Optional, Dict, Any
import logging
import uuid
from datetime import datetime
import json
import io

from app.core.config import settings
from app.models.schemas import DocumentResponse, DocumentMetadata
from app.services.storage import storage_service
from app.services.database import get_db
from app.routers.auth import get_current_user, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    document_type: str = Form("general"),
    tags: Optional[str] = Form(None),
    current_user: UserResponse = Depends(get_current_user)
):
    """Upload a document to MinIO storage"""
    try:
        # Validate file extension
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        if file_ext and f".{file_ext}" not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type .{file_ext} not allowed. Allowed types: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # Generate unique object name
        object_name = f"{current_user.tenant_id}/{uuid.uuid4()}/{file.filename}"
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Upload to MinIO
        await storage_service.upload_file(
            bucket_name=settings.MINIO_BUCKET_NAME,
            object_name=object_name,
            data=io.BytesIO(content),
            length=file_size,
            content_type=file.content_type
        )
        
        # Create document metadata (in production, save to PostgreSQL)
        document_id = str(uuid.uuid4())
        tags_list = tags.split(",") if tags else []
        
        logger.info(f"Document uploaded: {document_id} ({file.filename})")
        
        return DocumentResponse(
            id=document_id,
            title=title,
            filename=file.filename,
            object_name=object_name,
            document_type=document_type,
            description=description,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            tags=tags_list,
            uploaded_by=current_user.username,
            tenant_id=current_user.tenant_id,
            uploaded_at=datetime.utcnow().isoformat(),
            url=f"{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{object_name}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get document metadata by ID"""
    # In production, fetch from PostgreSQL
    # For demo, return mock data
    try:
        return DocumentResponse(
            id=document_id,
            title="Sample Document",
            filename="sample.pdf",
            object_name=f"{current_user.tenant_id}/{document_id}/sample.pdf",
            document_type="report",
            description="This is a sample document",
            file_size=1024000,
            mime_type="application/pdf",
            tags=["sample", "demo"],
            uploaded_by="admin",
            tenant_id=current_user.tenant_id,
            uploaded_at=datetime.utcnow().isoformat(),
            url=f"{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{current_user.tenant_id}/{document_id}/sample.pdf"
        )
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Download a document from MinIO"""
    try:
        # In production, fetch object_name from PostgreSQL
        object_name = f"{current_user.tenant_id}/{document_id}/sample.pdf"
        
        # Get presigned URL for download
        presigned_url = await storage_service.get_presigned_url(
            bucket_name=settings.MINIO_BUCKET_NAME,
            object_name=object_name,
            expires=3600  # 1 hour
        )
        
        return {"download_url": presigned_url, "expires_in": 3600}
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a document from storage"""
    try:
        # In production, fetch object_name from PostgreSQL
        object_name = f"{current_user.tenant_id}/{document_id}/sample.pdf"
        
        # Delete from MinIO
        await storage_service.delete_file(
            bucket_name=settings.MINIO_BUCKET_NAME,
            object_name=object_name
        )
        
        logger.info(f"Document deleted: {document_id}")
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-upload", response_model=List[DocumentResponse])
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    document_type: str = Form("general"),
    tags: Optional[str] = Form(None),
    current_user: UserResponse = Depends(get_current_user)
):
    """Upload multiple documents at once"""
    uploaded_documents = []
    
    for file in files:
        try:
            # Similar logic as single upload
            file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
            if file_ext and f".{file_ext}" not in settings.ALLOWED_EXTENSIONS:
                continue
            
            object_name = f"{current_user.tenant_id}/{uuid.uuid4()}/{file.filename}"
            content = await file.read()
            file_size = len(content)
            
            await storage_service.upload_file(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name,
                data=io.BytesIO(content),
                length=file_size,
                content_type=file.content_type
            )
            
            document_id = str(uuid.uuid4())
            tags_list = tags.split(",") if tags else []
            
            uploaded_documents.append(DocumentResponse(
                id=document_id,
                title=file.filename,
                filename=file.filename,
                object_name=object_name,
                document_type=document_type,
                file_size=file_size,
                mime_type=file.content_type or "application/octet-stream",
                tags=tags_list,
                uploaded_by=current_user.username,
                tenant_id=current_user.tenant_id,
                uploaded_at=datetime.utcnow().isoformat(),
                url=f"{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{object_name}"
            ))
        except Exception as e:
            logger.error(f"Failed to upload file {file.filename}: {e}")
            continue
    
    return uploaded_documents


@router.get("/search", response_model=Dict[str, Any])
async def search_documents(
    query: Optional[str] = None,
    document_type: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: UserResponse = Depends(get_current_user)
):
    """Search documents by metadata"""
    try:
        # In production, query PostgreSQL with filters
        # For demo, return mock results
        tag_list = tags.split(",") if tags else []
        
        return {
            "documents": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "filters": {
                "query": query,
                "document_type": document_type,
                "tags": tag_list
            }
        }
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))