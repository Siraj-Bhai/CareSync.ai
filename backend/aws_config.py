import os
import boto3
from secrets import get_secret

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = get_secret("BEDROCK_MODEL_ID")
S3_BUCKET = get_secret("S3_BUCKET", "caresync-voice")

# Separate credentials for Bedrock model calls
_model_session = boto3.Session(
    aws_access_key_id=get_secret("AWS_ACCESS_KEY_MODEL"),
    aws_secret_access_key=get_secret("AWS_SECRET_KEY_MODEL"),
    region_name=AWS_REGION,
)

# General AWS session (S3, etc.)
_aws_session = boto3.Session(
    aws_access_key_id=get_secret("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=get_secret("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION,
)

s3_client = _aws_session.client("s3")


def get_bedrock_model():
    """Returns a Strands BedrockModel using model-specific credentials."""
    from strands.models import BedrockModel
    return BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        boto_session=_model_session,
    )


async def upload_to_s3(file_bytes: bytes, key: str, content_type: str = "audio/webm") -> str:
    """Upload bytes to S3 and return the object URL."""
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
