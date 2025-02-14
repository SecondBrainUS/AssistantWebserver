from bson import ObjectId
from datetime import datetime
import json

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)

def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict using MongoJSONEncoder."""
    return json.loads(json.dumps(doc, cls=MongoJSONEncoder)) 