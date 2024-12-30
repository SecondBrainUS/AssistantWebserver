from bson import ObjectId
from datetime import datetime

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
    return doc 