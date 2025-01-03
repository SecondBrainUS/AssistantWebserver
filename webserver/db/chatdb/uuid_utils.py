from uuid import UUID
from typing import Union

def ensure_uuid(uuid_val: Union[str, UUID]) -> str:
    """Convert UUID to string format"""
    if isinstance(uuid_val, str):
        # Validate it's a proper UUID string
        UUID(uuid_val)  # This will raise ValueError if invalid
        return uuid_val
    elif isinstance(uuid_val, UUID):
        return str(uuid_val)
    raise ValueError(f"Cannot convert {type(uuid_val)} to UUID string")

# These functions now just pass through the string
def uuid_to_binary(uuid_str: Union[str, UUID]) -> str:
    return ensure_uuid(uuid_str)

def binary_to_uuid(uuid_str: str) -> str:
    return uuid_str 