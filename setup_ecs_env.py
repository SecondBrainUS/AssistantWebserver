import os
import json
import boto3
from pathlib import Path
from dotenv import dotenv_values

# === Load AWS Config from .env.aws.load ===
AWS_CONFIG_FILE = Path("env/.env.aws.load")
aws_config = dotenv_values(AWS_CONFIG_FILE)

SECRET_NAME = aws_config.get("SECRET_NAME")
AWS_REGION = aws_config.get("AWS_REGION")
SECRET_ENV_VAR = aws_config.get("SECRET_ENV_VAR")
PROFILE_NAME = aws_config.get("AWS_PROFILE")

# === Variable Classification ===
TASK_ENV_VARS = {
    "SYSTEM_MODE",
    "PORT",
    "ASSISTANTDB_URL",
    "MONGODB_URI",
    "MONGODB_DB_NAME",
    "MEMCACHE_HOST",
    "MEMCACHE_PORT",
    "S3_ENDPOINT",
    "BASE_URL",
    "FRONTEND_URL",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "SESSION_ID_EXPIRE_MINUTES",
    "MODELS_FILEPATH",
    "TIDAL_SECRETS_FILEPATH",
    "GCAL_CREDENTIALS_PATH",
}

def load_env(filepath):
    if not filepath.exists():
        raise FileNotFoundError(f"Env file not found: {filepath}")
    return dotenv_values(filepath)

def split_env_vars(env_dict):
    task_env = {}
    secrets = {}
    for key, value in env_dict.items():
        if key in TASK_ENV_VARS:
            task_env[key] = value
        else:
            secrets[key] = value
    return task_env, secrets

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[+] Wrote {filepath}")

def get_boto_client():
    session = boto3.Session(profile_name=PROFILE_NAME) if PROFILE_NAME else boto3.Session()
    return session.client("secretsmanager", region_name=AWS_REGION)

def get_account_id():
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]

def ensure_secret_exists(secret_name, secret_data):
    client = get_boto_client()
    try:
        client.describe_secret(SecretId=secret_name)
        print(f"[i] Secret {secret_name} already exists. Updating...")
        client.update_secret(SecretId=secret_name, SecretString=json.dumps(secret_data))
    except client.exceptions.ResourceNotFoundException:
        print(f"[+] Creating secret {secret_name}...")
        client.create_secret(Name=secret_name, SecretString=json.dumps(secret_data))

def main():
    dotenv_path = Path("env/.env.docker")
    print(f"[i] Loading env from {dotenv_path}")
    env_dict = load_env(dotenv_path)
    task_env, secrets = split_env_vars(env_dict)

    account_id = get_account_id()
    secret_arn = f"arn:aws:secretsmanager:{AWS_REGION}:{account_id}:secret:{SECRET_NAME}"

    # Save ECS environment and secrets JSON files
    save_json("ecs_task_env.json", [{"name": k, "value": v} for k, v in task_env.items()])
    save_json("ecs_secrets_block.json", [{"name": SECRET_ENV_VAR, "valueFrom": secret_arn}])

    # Upload combined secrets to AWS Secrets Manager
    ensure_secret_exists(SECRET_NAME, secrets)
    print("[✓] Done!")

if __name__ == "__main__":
    main()
