from uuid import UUID
from bson import Binary
from typing import Union

def uuid_to_binary(uuid_str: Union[str, UUID]) -> Binary:
    """Convert UUID string or UUID object to MongoDB Binary format"""
    if isinstance(uuid_str, str):
        uuid_obj = UUID(uuid_str)
    elif isinstance(uuid_str, UUID):
        uuid_obj = uuid_str
    else:
        raise ValueError(f"Expected str or UUID, got {type(uuid_str)}")
    return Binary.from_uuid(uuid_obj)

def binary_to_uuid(binary: Binary) -> UUID:
    """Convert MongoDB Binary back to UUID object"""
    return binary.as_uuid()

def ensure_uuid(uuid_val: Union[str, UUID, Binary]) -> UUID:
    """Ensure value is converted to UUID object"""
    if isinstance(uuid_val, str):
        return UUID(uuid_val)
    elif isinstance(uuid_val, Binary):
        return binary_to_uuid(uuid_val)
    elif isinstance(uuid_val, UUID):
        return uuid_val
    raise ValueError(f"Cannot convert {type(uuid_val)} to UUID") 