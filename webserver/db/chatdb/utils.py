from bson import ObjectId, Binary
from datetime import datetime
from uuid import UUID

def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict."""
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_doc(v) for v in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()  # Converts to ISO 8601 format string
    elif isinstance(doc, Binary):
        # Convert Binary UUID back to string representation
        try:
            return str(UUID(bytes=doc))
        except ValueError:
            return str(doc)
    return doc 