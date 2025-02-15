import requests
from typing import List, Dict
from webserver.config import settings

class SensorValuesClient:
    def __init__(self, sensor_values_host: str, sensor_values_group_id: str, sensor_values_metrics: List[str]):
        self.base_url = f"http://{sensor_values_host}/api/v1"
        self.group_id = sensor_values_group_id
        self.metrics = sensor_values_metrics

    def get_locations(self) -> List[Dict]:
        url = f"{self.base_url}/locationgroup/{self.group_id}/locations"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("locations", [])
        else:
            raise Exception(f"Failed to get locations: {response.status_code}")

    def get_location_id_by_name(self, location_name: str) -> str:
        locations = self.get_locations()
        for location in locations:
            if location.get("name").lower() == location_name.lower():
                return location.get("locationid")
        raise Exception(f"Location '{location_name}' not found")

    def get_metric_value(self, location_id: str, metric: str) -> Dict:
        url = f"{self.base_url}/location/{location_id}/current/{metric}"
        print(f"Attempting to fetch from URL: {url}")  # Debug print
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return {
                "value": data.get("value"),
                "unit": data.get("unit")
            }
        else:
            error_message = response.json().get("detail", f"Failed to get {metric} data: {response.status_code}")
            return {
                "status": "error",
                "detail": error_message
            }

# Create a single instance to be used by all functions
client = SensorValuesClient(
    sensor_values_host=settings.SENSOR_VALUES_HOST_CRITTENDEN,
    sensor_values_group_id=settings.SENSOR_VALUES_CRITTENDEN_GROUP_ID,
    sensor_values_metrics=settings.SENSOR_VALUES_METRICS
)

def get_tool_function_map():
    """Get the tool function map for Sensor Values-related functions"""
    tool_function_map = {
        "sensor_get_locations": {
            "function": client.get_locations,
            "description": "Get a list of available sensor locations",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        "sensor_get_metric_value": {
            "function": client.get_metric_value,
            "description": "Get the current value of a specific metric for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location_id": {
                        "type": "string",
                        "description": "ID of the location to get metrics for",
                    },
                    "metric": {
                        "type": "string",
                        "description": "Name of the metric to retrieve",
                    },
                },
                "required": ["location_id", "metric"],
            },
        },
        "sensor_get_location_id_by_name": {
            "function": client.get_location_id_by_name,
            "description": "Get the location ID for a given location name",
            "parameters": {
                "type": "object",
                "properties": {
                    "location_name": {
                        "type": "string",
                        "description": "Name of the location to look up",
                    },
                },
                "required": ["location_name"],
            },
        },
    }
    return tool_function_map 