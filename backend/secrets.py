import boto3
import json
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def get_secrets():
    """Fetch all secrets from AWS Secrets Manager"""
    secret_name = os.getenv("SECRET_NAME", "backend-env")
    region = os.getenv("AWS_REGION", "us-east-1")
    
    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except Exception as e:
        print(f"Error fetching secrets: {e}")
        return {}

def get_secret(key: str, default=None):
    """Get a specific secret value"""
    secrets = get_secrets()
    return secrets.get(key, os.getenv(key, default))
