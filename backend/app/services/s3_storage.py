"""
S3 Storage Service

Handles file uploads and downloads to AWS S3 for resumes and other documents.
"""

import io
import json
import os
from datetime import datetime, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError


# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "hireright-storage")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def get_s3_client():
    """Get configured S3 client."""
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


# =============================================================================
# Resume Operations
# =============================================================================

async def upload_resume(
    user_id: str,
    file_content: bytes,
    filename: str,
    content_type: str = "application/pdf",
) -> dict:
    """
    Upload a resume PDF to S3.
    
    Args:
        user_id: User's unique ID
        file_content: Raw bytes of the PDF
        filename: Original filename
        content_type: MIME type
        
    Returns:
        dict with s3_key and url
    """
    s3 = get_s3_client()
    
    # Generate unique S3 key
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    s3_key = f"resumes/raw/{user_id}_{timestamp}_{filename}"
    
    try:
        s3.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
            Metadata={
                "user_id": user_id,
                "original_filename": filename,
                "uploaded_at": timestamp,
            },
        )
        
        return {
            "success": True,
            "s3_key": s3_key,
            "bucket": AWS_S3_BUCKET,
            "url": f"s3://{AWS_S3_BUCKET}/{s3_key}",
        }
    except ClientError as e:
        return {
            "success": False,
            "error": str(e),
        }


async def upload_parsed_resume(
    user_id: str,
    parsed_data: dict,
) -> dict:
    """
    Upload parsed resume JSON to S3.
    
    Args:
        user_id: User's unique ID
        parsed_data: Parsed resume data as dictionary
        
    Returns:
        dict with s3_key and url
    """
    s3 = get_s3_client()
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    s3_key = f"resumes/parsed/{user_id}_{timestamp}.json"
    
    try:
        s3.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(parsed_data, indent=2, default=str),
            ContentType="application/json",
            Metadata={
                "user_id": user_id,
                "parsed_at": timestamp,
            },
        )
        
        return {
            "success": True,
            "s3_key": s3_key,
            "bucket": AWS_S3_BUCKET,
            "url": f"s3://{AWS_S3_BUCKET}/{s3_key}",
        }
    except ClientError as e:
        return {
            "success": False,
            "error": str(e),
        }


async def download_resume(s3_key: str) -> Optional[bytes]:
    """
    Download a resume from S3.
    
    Args:
        s3_key: S3 object key
        
    Returns:
        File content as bytes, or None if not found
    """
    s3 = get_s3_client()
    
    try:
        response = s3.get_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
        )
        return response["Body"].read()
    except ClientError:
        return None


async def get_presigned_url(
    s3_key: str,
    expiration: int = 3600,
) -> Optional[str]:
    """
    Generate a presigned URL for secure temporary access.
    
    Args:
        s3_key: S3 object key
        expiration: URL expiration time in seconds (default: 1 hour)
        
    Returns:
        Presigned URL or None if error
    """
    s3 = get_s3_client()
    
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": AWS_S3_BUCKET,
                "Key": s3_key,
            },
            ExpiresIn=expiration,
        )
        return url
    except ClientError:
        return None


async def list_user_resumes(user_id: str) -> list[dict]:
    """
    List all resumes for a user.
    
    Args:
        user_id: User's unique ID
        
    Returns:
        List of resume metadata
    """
    s3 = get_s3_client()
    
    try:
        response = s3.list_objects_v2(
            Bucket=AWS_S3_BUCKET,
            Prefix=f"resumes/raw/{user_id}_",
        )
        
        resumes = []
        for obj in response.get("Contents", []):
            resumes.append({
                "s3_key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            })
        
        return resumes
    except ClientError:
        return []


async def delete_resume(s3_key: str) -> bool:
    """
    Delete a resume from S3.
    
    Args:
        s3_key: S3 object key
        
    Returns:
        True if deleted successfully
    """
    s3 = get_s3_client()
    
    try:
        s3.delete_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
        )
        return True
    except ClientError:
        return False


# =============================================================================
# Cover Letter Operations
# =============================================================================

async def upload_cover_letter(
    user_id: str,
    job_id: str,
    content: str,
    format: str = "txt",
) -> dict:
    """
    Upload a generated cover letter.
    
    Args:
        user_id: User's unique ID
        job_id: Job ID this cover letter is for
        content: Cover letter content
        format: File format (txt or pdf)
        
    Returns:
        dict with s3_key and url
    """
    s3 = get_s3_client()
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    s3_key = f"exports/cover_letters/{user_id}_{job_id}_{timestamp}.{format}"
    
    content_type = "text/plain" if format == "txt" else "application/pdf"
    body = content if isinstance(content, bytes) else content.encode("utf-8")
    
    try:
        s3.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            Body=body,
            ContentType=content_type,
            Metadata={
                "user_id": user_id,
                "job_id": job_id,
                "generated_at": timestamp,
            },
        )
        
        return {
            "success": True,
            "s3_key": s3_key,
            "bucket": AWS_S3_BUCKET,
            "url": f"s3://{AWS_S3_BUCKET}/{s3_key}",
        }
    except ClientError as e:
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# Utility Functions
# =============================================================================

def check_s3_connection() -> dict:
    """
    Check if S3 connection is working.
    
    Returns:
        dict with connection status
    """
    s3 = get_s3_client()
    
    try:
        s3.head_bucket(Bucket=AWS_S3_BUCKET)
        return {
            "connected": True,
            "bucket": AWS_S3_BUCKET,
            "region": AWS_REGION,
        }
    except ClientError as e:
        return {
            "connected": False,
            "error": str(e),
        }
