from uuid import UUID

def ensure_uuid(uuid_val: str) -> str:
    """Validate and return UUID string format"""
    if not isinstance(uuid_val, str):
        raise ValueError(f"UUID must be string, got {type(uuid_val)}")
    # Validate it's a proper UUID string
    UUID(uuid_val)  # This will raise ValueError if invalid
    return uuid_val