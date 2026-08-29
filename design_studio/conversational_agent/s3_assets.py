"""S3 helpers for uploading screenshots and generating pre-signed share URLs."""

from __future__ import annotations

import os

import boto3

REGION = os.environ.get("AWS_REGION", "eu-north-1")

_s3 = None


def _client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=REGION)
    return _s3


def upload_png(bucket: str, key: str, png_bytes: bytes) -> None:
    _client().put_object(
        Bucket=bucket,
        Key=key,
        Body=png_bytes,
        ContentType="image/png",
    )


def generate_share_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
