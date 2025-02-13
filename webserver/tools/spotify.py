from webserver.config import settings
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import logging


logger = logging.getLogger(__name__)
logger.info(f"SPOTIFY_REDIRECT_URI: {settings.SPOTIFY_REDIRECT_URI}")

sp_oauth = SpotifyOAuth(
    client_id=settings.SPOTIFY_CLIENT_ID,
    client_secret=settings.SPOTIFY_CLIENT_SECRET,
    redirect_uri=settings.SPOTIFY_REDIRECT_URI,
    scope=settings.SPOTIFY_SCOPES,
    cache_path="./secrets/cache-service-account.json"
)

# Create a global Spotify client
sp = spotipy.Spotify(auth_manager=sp_oauth)

def get_devices() -> list:
    devices = sp.devices()
    return devices.get("devices", [])

def get_show(show_name: str, market: str = "US") -> dict:
    result = sp.search(q=show_name, type="show", market=market, limit=1)
    shows = result.get("shows", {}).get("items", [])
    return shows[0] if shows else None

def get_show_episodes(show_id: str, limit: int = 20, offset: int = 0, market: str = "US") -> dict:
    return sp.show_episodes(show_id, limit=limit, offset=offset, market=market)

def create_playlist(user_id: str, playlist_name: str, description: str, public: bool = False) -> dict:
    return sp.user_playlist_create(user=user_id, name=playlist_name, public=public, description=description)

def add_song_to_playlist(playlist_id: str, track_uris: list) -> dict:
    return sp.playlist_add_items(playlist_id, track_uris)

def play_song_by_id(song_id: str, device_id: str) -> None:
    uri = f"spotify:track:{song_id}"
    sp.start_playback(device_id=device_id, uris=[uri])

def play_episode_by_id(episode_id: str, device_id: str) -> None:
    uri = f"spotify:episode:{episode_id}"
    sp.start_playback(device_id=device_id, uris=[uri])

def play_show_by_id(show_id: str, device_id: str, market: str = "US") -> None:
    episodes = get_show_episodes(show_id, limit=1, market=market)
    items = episodes.get("items", [])
    if not items:
        raise Exception("No episodes found for this show.")
    first_episode_id = items[0]["id"]
    play_episode_by_id(first_episode_id, device_id)

def get_tool_function_map():
    """Get the tool function map for Spotify-related functions"""
    tool_function_map = {
        "get_devices": {
            "function": get_devices,
            "description": "Get a list of available Spotify devices",
            "parameters": {
                "type": "object",
                "properties": {},  # No parameters needed
            },
        },
        "get_show": {
            "function": get_show,
            "description": "Search for a Spotify show by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_name": {
                        "type": "string",
                        "description": "Name of the show to search for",
                    },
                    "market": {
                        "type": "string",
                        "description": "Market code (e.g., 'US')",
                        "default": "US",
                    },
                },
                "required": ["show_name"],
            },
        },
        "play_song_by_id": {
            "function": play_song_by_id,
            "description": "Play a specific song on a Spotify device",
            "parameters": {
                "type": "object",
                "properties": {
                    "song_id": {
                        "type": "string",
                        "description": "Spotify ID of the song to play",
                    },
                    "device_id": {
                        "type": "string",
                        "description": "ID of the Spotify device to play on",
                    },
                },
                "required": ["song_id", "device_id"],
            },
        },
        "play_episode_by_id": {
            "function": play_episode_by_id,
            "description": "Play a specific podcast episode on a Spotify device",
            "parameters": {
                "type": "object",
                "properties": {
                    "episode_id": {
                        "type": "string",
                        "description": "Spotify ID of the episode to play",
                    },
                    "device_id": {
                        "type": "string",
                        "description": "ID of the Spotify device to play on",
                    },
                },
                "required": ["episode_id", "device_id"],
            },
        },
        "play_show_by_id": {
            "function": play_show_by_id,
            "description": "Play the latest episode of a show on a Spotify device",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_id": {
                        "type": "string",
                        "description": "Spotify ID of the show to play",
                    },
                    "device_id": {
                        "type": "string",
                        "description": "ID of the Spotify device to play on",
                    },
                    "market": {
                        "type": "string",
                        "description": "Market code (e.g., 'US')",
                        "default": "US",
                    },
                },
                "required": ["show_id", "device_id"],
            },
        },
    }
    return tool_function_map

if __name__ == "__main__":
    # Test get_devices
    print("\nTesting get_devices():")
    devices = get_devices()
    for device in devices:
        print(f"Device: {device['name']} (ID: {device['id']})")

    # Test get_show for "acquired"
    print("\nTesting get_show() for 'acquired':")
    show = get_show("acquired")
    if show:
        print(f"Show found: {show['name']}")
        print(f"Description: {show['description'][:100]}...")
        print(f"Publisher: {show['publisher']}")
    else:
        print("Show not found")