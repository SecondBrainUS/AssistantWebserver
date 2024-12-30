from bson import ObjectId, Binary
from datetime import datetime
from uuid import UUID
from webserver.db.chatdb.uuid_utils import binary_to_uuid

def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict."""
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_doc(v) for v in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    elif isinstance(doc, Binary):
        try:
            # Convert Binary UUID to string representation
            return str(binary_to_uuid(doc))
        except Exception:
            return str(doc)
    elif isinstance(doc, UUID):
        return str(doc)
    return doc 