from webserver.config import settings
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import logging
import difflib

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

def get_show(show_name: str, market: str = "US", limit: int = 5) -> list:
    """
    Search for Spotify shows by name and return top matches.
    
    :param show_name: Name of the show to search for
    :param market: Market code (default: 'US')
    :param limit: Number of top results to return (default: 5)
    :return: List of matching shows sorted by similarity score
    """
    result = sp.search(q=show_name, type="show", market=market, limit=25)
    shows = result.get("shows", {}).get("items", [])
    
    if not shows:
        return []
        
    # Score all shows using fuzzy matching
    scored_shows = []
    for show in shows:
        similarity = difflib.SequenceMatcher(None, show_name.lower(), show['name'].lower()).ratio()
        if similarity > 0.5:  # Only include reasonably good matches
            scored_shows.append((similarity, show))
    
    # Sort by score (first element of tuple) and return top matches
    scored_shows.sort(key=lambda x: x[0], reverse=True)
    return [show for score, show in scored_shows[:limit]]

def get_show_episodes(show_id: str, limit: int = 20, offset: int = 0, market: str = "US") -> dict:
    return sp.show_episodes(show_id, limit=limit, offset=offset, market=market)

def create_playlist(user_id: str, playlist_name: str, description: str, public: bool = False) -> dict:
    """
    Create a new Spotify playlist for the specified user.
    
    :param user_id: Spotify user ID to create the playlist for
    :param playlist_name: Name of the new playlist
    :param description: Description of the playlist
    :param public: Whether the playlist should be public (default: False)
    :return: Dictionary containing the created playlist details including:
            - id: The playlist's Spotify ID
            - name: The playlist's name
            - uri: The playlist's Spotify URI
            - external_urls: URLs to access the playlist
            - owner: Information about the playlist owner
    :raises Exception: If playlist creation fails
    """
    try:
        logger.info(f"Creating playlist '{playlist_name}' for user {user_id}")
        playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=public, description=description)
        logger.info(f"Successfully created playlist: {playlist.get('name')} (ID: {playlist.get('id')})")
        return playlist
    except Exception as e:
        logger.error(f"Failed to create playlist: {str(e)}")
        raise Exception(f"Failed to create playlist: {str(e)}") from e

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

def get_playlist(playlist_id: str, market: str = "US") -> dict:
    """
    Retrieve details of a Spotify playlist.

    :param playlist_id: The Spotify ID of the playlist (must be a valid base62 ID).
    :param market: Optional market code (default: 'US').
    :return: Dictionary containing the playlist details.
    """
    try:
        return sp.playlist(playlist_id, market=market)
    except Exception as e:
        logger.error("Error retrieving playlist with id %s: %s", playlist_id, e)
        raise ValueError(
            f"Invalid playlist id '{playlist_id}'. Please provide a valid Spotify playlist id (typically a 22-character base62 string)."
        ) from e

def search_song(song_name: str, market: str = "US", artist_name: str = None, album_name: str = None, limit: int = 5) -> list:
    """
    Search for songs on Spotify and return top matches.

    :param song_name: The name of the song to search for
    :param market: Optional market code (default: 'US')
    :param artist_name: Optional artist name to further refine the search
    :param album_name: Optional album name to further refine the search
    :param limit: Number of top results to return (default: 5)
    :return: List of matching tracks sorted by similarity score
    """
    query = f'track:"{song_name}"'
    if artist_name:
        query += f' artist:"{artist_name}"'
    if album_name:
        query += f' album:"{album_name}"'

    result = sp.search(q=query, type="track", market=market, limit=25)
    tracks = result.get("tracks", {}).get("items", [])
    
    if not tracks:
        return []

    scored_tracks = []
    for track in tracks:
        similarity = difflib.SequenceMatcher(None, song_name.lower(), track["name"].lower()).ratio()
        if similarity > 0.5:  # Only include reasonably good matches
            scored_tracks.append((similarity, track))

    # Sort by score (first element of tuple) and return top matches
    scored_tracks.sort(key=lambda x: x[0], reverse=True)
    return [track for score, track in scored_tracks[:limit]]

def get_playlist_by_name(playlist_name: str, market: str = "US", limit: int = 5) -> list:
    """
    Search for Spotify playlists by name among the current user's playlists.

    :param playlist_name: The name of the playlist to search for
    :param market: Optional market code (default: 'US')
    :param limit: Number of top results to return (default: 5)
    :return: List of matching playlists sorted by similarity score
    """
    results = sp.current_user_playlists()
    playlists = results['items']
    
    while results['next']:
        results = sp.next(results)
        playlists.extend(results['items'])

    if not playlists:
        return []

    scored_playlists = []
    for playlist in playlists:
        if not playlist or "name" not in playlist:
            continue
        similarity = difflib.SequenceMatcher(None, playlist_name.lower(), playlist["name"].lower()).ratio()
        if similarity > 0.5:  # Only include reasonably good matches
            scored_playlists.append((similarity, playlist))

    # Sort by score (first element of tuple) and return top matches
    scored_playlists.sort(key=lambda x: x[0], reverse=True)
    return [playlist for score, playlist in scored_playlists[:limit]]

def get_playlist_tracks(playlist_id: str, market: str = "US") -> dict:
    """
    Get all tracks from a Spotify playlist.
    
    :param playlist_id: The Spotify ID of the playlist
    :param market: Optional market code (default: 'US')
    :return: List of tracks with their details
    """
    try:
        results = sp.playlist_tracks(playlist_id, market=market)
        tracks = []
        
        # Process initial results
        for item in results['items']:
            if item['track']:
                track = item['track']
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown',
                    'album': track['album']['name'] if track['album'] else None,
                    'duration_ms': track['duration_ms'],
                    'uri': track['uri']
                })
        
        # Get remaining tracks if playlist is longer than 100 tracks
        while results['next']:
            results = sp.next(results)
            for item in results['items']:
                if item['track']:
                    track = item['track']
                    tracks.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown',
                        'album': track['album']['name'] if track['album'] else None,
                        'duration_ms': track['duration_ms'],
                        'uri': track['uri']
                    })
        
        return {'tracks': tracks, 'total': len(tracks)}
    except Exception as e:
        logger.error(f"Error getting playlist tracks: {str(e)}")
        raise Exception(f"Error getting playlist tracks: {str(e)}") from e

def get_current_user() -> dict:
    """
    Get the current user's Spotify profile information.
    
    :return: Dictionary containing user profile information including:
            - id: The user's Spotify ID
            - display_name: The user's display name
            - email: The user's email (if available)
            - country: The user's country code
            - product: The user's Spotify subscription level
    :raises Exception: If retrieving user profile fails
    """
    try:
        return sp.current_user()
    except Exception as e:
        logger.error(f"Failed to get current user profile: {str(e)}")
        raise Exception(f"Failed to get current user profile: {str(e)}") from e

def get_tool_function_map():
    """Get the tool function map for Spotify-related functions"""
    tool_function_map = {
        "spotify_get_devices": {
            "function": get_devices,
            "description": "Get a list of available Spotify devices",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        "spotify_get_show": {
            "function": get_show,
            "description": "Search for Spotify shows by name and return top matches",
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
                    "limit": {
                        "type": "integer",
                        "description": "Number of top results to return",
                        "default": 5,
                    },
                },
                "required": ["show_name"],
            },
        },
        "spotify_get_show_episodes": {
            "function": get_show_episodes,
            "description": "Get episodes for a specific Spotify show",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_id": {
                        "type": "string",
                        "description": "Spotify ID of the show",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of episodes to return",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of episodes to skip",
                        "default": 0,
                    },
                    "market": {
                        "type": "string",
                        "description": "Market code (e.g., 'US')",
                        "default": "US",
                    },
                },
                "required": ["show_id"],
            },
        },
        "spotify_play_song_by_id": {
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
        "spotify_play_episode_by_id": {
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
        "spotify_play_show_by_id": {
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
        "spotify_get_playlist": {
            "function": get_playlist,
            "description": "Retrieve details of a Spotify playlist by its ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_id": {
                        "type": "string",
                        "description": "Spotify ID of the playlist",
                    },
                    "market": {
                        "type": "string",
                        "description": "Market code (e.g., 'US')",
                        "default": "US",
                    },
                },
                "required": ["playlist_id"],
            },
        },
        "spotify_get_playlist_by_name": {
            "function": get_playlist_by_name,
            "description": "Search for Spotify playlists by name and return top matches",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_name": {
                        "type": "string",
                        "description": "Name of the playlist to search for",
                    },
                    "market": {
                        "type": "string",
                        "description": "Market code (e.g., 'US')",
                        "default": "US",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top results to return",
                        "default": 5,
                    },
                },
                "required": ["playlist_name"],
            },
        },
        "spotify_add_song_to_playlist": {
            "function": add_song_to_playlist,
            "description": "Add songs to a Spotify playlist using its playlist ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_id": {
                        "type": "string",
                        "description": "Spotify playlist ID (base62 string)",
                    },
                    "track_uris": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of track URIs to add to the playlist",
                    },
                },
                "required": ["playlist_id", "track_uris"],
            },
        },
        "spotify_search_song": {
            "function": search_song,
            "description": "Search for songs on Spotify and return top matches",
            "parameters": {
                "type": "object",
                "properties": {
                    "song_name": {
                        "type": "string",
                        "description": "Name of the song to search for",
                    },
                    "market": {
                        "type": "string",
                        "description": "Market code (default is 'US')",
                        "default": "US",
                    },
                    "artist_name": {
                        "type": "string",
                        "description": "Optional artist name to narrow down the search",
                    },
                    "album_name": {
                        "type": "string",
                        "description": "Optional album name to narrow down the search",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top results to return",
                        "default": 5,
                    },
                },
                "required": ["song_name"],
            },
        },
        "spotify_create_playlist": {
            "function": create_playlist,
            "description": "Create a new Spotify playlist for a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Spotify user ID to create the playlist for",
                    },
                    "playlist_name": {
                        "type": "string",
                        "description": "Name of the new playlist",
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the playlist",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Whether the playlist should be public",
                        "default": False,
                    },
                },
                "required": ["user_id", "playlist_name", "description"],
            },
        },
        "spotify_get_playlist_tracks": {
            "function": get_playlist_tracks,
            "description": "Get all tracks from a Spotify playlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_id": {
                        "type": "string",
                        "description": "Spotify playlist ID (base62 string)",
                    },
                    "market": {
                        "type": "string",
                        "description": "Market code (e.g., 'US')",
                        "default": "US",
                    },
                },
                "required": ["playlist_id"],
            },
        },
        "spotify_get_current_user": {
            "function": get_current_user,
            "description": "Get the current user's Spotify profile information",
            "parameters": {
                "type": "object",
                "properties": {},
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
    shows = get_show("acquired")
    if shows:
        for show in shows:
            print(f"Show found: {show['name']}")
            print(f"Description: {show['description'][:100]}...")
            print(f"Publisher: {show['publisher']}")
    else:
        print("No shows found")