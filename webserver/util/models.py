import json
import os
from webserver.config import settings

def load_models():
    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.MODELS_FILEPATH)
    with open(filepath, 'r') as f:
        return json.load(f)

def get_model_by_id(model_id: str):
    models = load_models()
    for model in models['models']:
        if model['model_id'] == model_id:
            return model
    return None