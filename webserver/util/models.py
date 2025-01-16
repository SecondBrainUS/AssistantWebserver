import json
from webserver.config import settings

def load_models():
    with open(settings.MODELS_FILEPATH, 'r') as f:
        return json.load(f)

def get_model_by_id(model_id: str):
    models = load_models()
    for model in models['models']:
        if model['model_id'] == model_id:
            return model
    return None