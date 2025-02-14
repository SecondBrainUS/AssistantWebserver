from pathlib import Path
import difflib
import webbrowser
import tidalapi
import tidalapi.exceptions
import logging

logger = logging.getLogger(__name__)

# Initialize the session globally
def get_session():
    session = tidalapi.Session()
    session_path = Path("secrets/tidal_session.json")

    # Load session from file or create a new one if loading fails
    if session_path.exists():
        try:
            if session.login_session_file(session_path):
                logger.info("Tidal session successfully loaded from file.")
                return session
        except tidalapi.exceptions.AuthenticationError as e:
            logger.error(f"Failed to load cached Tidal session: {e}")

    # If loading fails, initiate a new OAuth session
    login, future = session.login_oauth()

    # Open the browser for user authentication
    try:
        webbrowser.open(login.verification_uri_complete)
        logger.info("A browser window has been opened for Tidal authentication.")
    except Exception as e:
        logger.error(f"Failed to open browser for Tidal auth: {e}")
        logger.info(f"Please open: {login.verification_uri_complete}")

    # Wait for the user to complete authentication
    future.result()

    # Save the authenticated session
    session.login_session_file(session_path)
    logger.info("Tidal authentication successful and session saved.")

    return session

def create_playlist(playlist_name: str, playlist_description: str) -> dict:
    """Create a new Tidal playlist."""
    try:
        session = get_session()
        session.user.create_playlist(playlist_name, playlist_description)
        return {"message": f"Successfully created playlist: {playlist_name}"}
    except Exception as e:
        logger.error(f"Failed to create Tidal playlist: {e}")
        raise Exception(f"Failed to create Tidal playlist: {str(e)}") from e

def get_playlist_by_name(playlist_name: str) -> dict:
    """Get a Tidal playlist by name using fuzzy matching."""
    try:
        session = get_session()
        playlists = session.user.playlists()
        
        # Extract playlist names for fuzzy matching
        playlist_names = [p.name for p in playlists]
        close_matches = difflib.get_close_matches(playlist_name, playlist_names, n=1, cutoff=0.5)
        
        if not close_matches:
            return {"message": f"No playlists found matching '{playlist_name}'"}
            
        matched_name = close_matches[0]
        playlist = next((p for p in playlists if p.name == matched_name), None)
        
        if playlist:
            return {
                "id": playlist.id,
                "name": playlist.name,
                "description": playlist.description,
                "numberOfTracks": playlist.num_tracks
            }
        return {"message": "No matching playlist found"}
        
    except Exception as e:
        logger.error(f"Error getting Tidal playlist: {e}")
        raise Exception(f"Error getting Tidal playlist: {str(e)}") from e

def add_song_to_playlist(playlist_name: str, song_name: str, artist_name: str = None, album_name: str = None) -> dict:
    """Add a song to a Tidal playlist."""
    try:
        session = get_session()
        
        # Get the playlist
        playlists = session.user.playlists()
        playlist_names = [p.name for p in playlists]
        close_matches = difflib.get_close_matches(playlist_name, playlist_names, n=1, cutoff=0.5)
        
        if not close_matches:
            return {"message": f"No playlists found matching '{playlist_name}'"}
            
        playlist = next((p for p in playlists if p.name == close_matches[0]), None)
        
        # Search for the song
        search_query = song_name
        if artist_name:
            search_query += f" {artist_name}"
        if album_name:
            search_query += f" {album_name}"
            
        search_results = session.search(query=search_query, models=[tidalapi.media.Track])
        tracks = search_results.get('tracks', [])
        
        if not tracks:
            return {"message": f"No tracks found for '{search_query}'"}
            
        # Find best matching track
        best_track = None
        best_score = 0
        for track in tracks:
            score = difflib.SequenceMatcher(None, song_name.lower(), track.name.lower()).ratio()
            if artist_name and track.artist:
                score += difflib.SequenceMatcher(None, artist_name.lower(), track.artist.name.lower()).ratio()
            if album_name and track.album:
                score += difflib.SequenceMatcher(None, album_name.lower(), track.album.name.lower()).ratio()
            if score > best_score:
                best_score = score
                best_track = track
                
        if best_track:
            playlist.add([best_track.id])
            return {
                "message": f"Added '{best_track.name}' by '{best_track.artist.name}' to playlist '{playlist.name}'",
                "track": {
                    "id": best_track.id,
                    "name": best_track.name,
                    "artist": best_track.artist.name,
                    "album": best_track.album.name if best_track.album else None
                }
            }
        return {"message": f"No suitable track found for '{search_query}'"}
        
    except Exception as e:
        logger.error(f"Error adding song to Tidal playlist: {e}")
        raise Exception(f"Error adding song to Tidal playlist: {str(e)}") from e

def get_playlistid_by_name(playlist_name: str) -> dict:
    """Get a Tidal playlist ID by name using fuzzy matching."""
    try:
        session = get_session()
        
        # Get the playlist
        try:
            playlists = session.user.playlists()
        except tidalapi.exceptions.TidalError as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                return {
                    "message": "Rate limit exceeded. Please wait a moment before trying again.",
                    "error": "RATE_LIMIT"
                }
            raise

        playlist_names = [p.name for p in playlists]
        close_matches = difflib.get_close_matches(playlist_name, playlist_names, n=1, cutoff=0.5)
        
        if not close_matches:
            return {"message": f"No playlists found matching '{playlist_name}'"}
            
        playlist = next((p for p in playlists if p.name == close_matches[0]), None)
        
        if not playlist:
            return {"message": "No matching playlist found"}
            
        return {
            "playlist_id": playlist.id,
            "playlist_name": playlist.name,
            "description": getattr(playlist, 'description', None),
            "numberOfTracks": getattr(playlist, 'num_tracks', 0)
        }
        
    except tidalapi.exceptions.TidalError as e:
        if hasattr(e, 'status_code') and e.status_code == 429:
            logger.warning("Tidal rate limit exceeded")
            return {
                "message": "Rate limit exceeded. Please wait a moment before trying again.",
                "error": "RATE_LIMIT"
            }
        logger.error(f"Tidal API error: {e}")
        raise Exception(f"Tidal API error: {str(e)}") from e
    except Exception as e:
        logger.error(f"Error getting Tidal playlist: {e}")
        raise Exception(f"Error getting Tidal playlist: {str(e)}") from e

def get_playlist_tracks_by_playlistid(playlist_id: str) -> dict:
    """Get all tracks from a Tidal playlist using the playlist ID."""
    try:
        session = get_session()
        
        try:
            playlist = session.playlist(playlist_id)
        except tidalapi.exceptions.TidalError as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                return {
                    "message": "Rate limit exceeded. Please wait a moment before trying again.",
                    "error": "RATE_LIMIT"
                }
            raise
            
        if not playlist:
            return {"message": f"No playlist found with ID: {playlist_id}"}
            
        # Get all tracks
        try:
            tracks = playlist.tracks()
        except tidalapi.exceptions.TidalError as e:
            if hasattr(e, 'status_code') and e.status_code == 429:
                return {
                    "message": "Rate limit exceeded. Please wait a moment before trying again.",
                    "error": "RATE_LIMIT"
                }
            raise

        track_list = []
        
        for track in tracks:
            try:
                track_data = {
                    'id': getattr(track, 'id', None),
                    'name': getattr(track, 'name', 'Unknown Track'),
                    'artist': getattr(track.artist, 'name', 'Unknown Artist') if hasattr(track, 'artist') else 'Unknown Artist',
                    'album': getattr(track.album, 'name', None) if hasattr(track, 'album') else None,
                    'duration_ms': getattr(track, 'duration', 0) * 1000 if hasattr(track, 'duration') else None,
                }
                
                # Safely get URL with rate limit handling
                try:
                    # track_data['tidal_url'] = track.get_url() if hasattr(track, 'get_url') else None
                    track_data['tidal_url'] = None
                except tidalapi.exceptions.TidalError as e:
                    if hasattr(e, 'status_code') and e.status_code == 429:
                        track_data['tidal_url'] = None
                        logger.warning(f"Rate limit hit while getting URL for track {track_data['name']}")
                    else:
                        raise
                
                track_list.append(track_data)
                
            except Exception as track_error:
                logger.warning(f"Error processing track data: {track_error}")
                continue
        
        if not track_list:
            return {
                "message": "No tracks could be retrieved from the playlist",
                "playlist_name": getattr(playlist, 'name', None),
                "playlist_id": playlist_id
            }
        
        return {
            'playlist_name': getattr(playlist, 'name', None),
            'playlist_id': playlist_id,
            'tracks': track_list,
            'total': len(track_list)
        }
        
    except tidalapi.exceptions.TidalError as e:
        if hasattr(e, 'status_code') and e.status_code == 429:
            logger.warning("Tidal rate limit exceeded")
            return {
                "message": "Rate limit exceeded. Please wait a moment before trying again.",
                "error": "RATE_LIMIT"
            }
        logger.error(f"Tidal API error: {e}")
        raise Exception(f"Tidal API error: {str(e)}") from e
    except Exception as e:
        logger.error(f"Error getting Tidal playlist tracks: {e}")
        raise Exception(f"Error getting Tidal playlist tracks: {str(e)}") from e

def get_playlist_tracks(playlist_name: str) -> dict:
    """Get all tracks from a Tidal playlist using fuzzy matching for the playlist name."""
    # Get playlist ID first
    playlist_info = get_playlistid_by_name(playlist_name)
    
    # Check for errors or no playlist found
    if "error" in playlist_info or "message" in playlist_info:
        return playlist_info
        
    # Get tracks using the playlist ID
    return get_playlist_tracks_by_playlistid(playlist_info["playlist_id"])

def get_tool_function_map():
    """Get the tool function map for Tidal-related functions"""
    tool_function_map = {
        "tidal_create_playlist": {
            "function": create_playlist,
            "description": "Create a new Tidal playlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_name": {
                        "type": "string",
                        "description": "Name of the playlist to create"
                    },
                    "playlist_description": {
                        "type": "string",
                        "description": "Description of the playlist"
                    }
                },
                "required": ["playlist_name", "playlist_description"]
            }
        },
        "tidal_get_playlist_by_name": {
            "function": get_playlist_by_name,
            "description": "Get a Tidal playlist by name using fuzzy matching",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_name": {
                        "type": "string",
                        "description": "Name of the playlist to search for"
                    }
                },
                "required": ["playlist_name"]
            }
        },
        "tidal_add_song_to_playlist": {
            "function": add_song_to_playlist,
            "description": "Add a song to a Tidal playlist",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_name": {
                        "type": "string",
                        "description": "Name of the playlist to add the song to"
                    },
                    "song_name": {
                        "type": "string",
                        "description": "Name of the song to add"
                    },
                    "artist_name": {
                        "type": "string",
                        "description": "Optional artist name to refine the search"
                    },
                    "album_name": {
                        "type": "string",
                        "description": "Optional album name to refine the search"
                    }
                },
                "required": ["playlist_name", "song_name"]
            }
        },
        "tidal_get_playlistid_by_name": {
            "function": get_playlistid_by_name,
            "description": "Get a Tidal playlist ID by name using fuzzy matching",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_name": {
                        "type": "string",
                        "description": "Name of the playlist to search for"
                    }
                },
                "required": ["playlist_name"]
            }
        },
        "tidal_get_playlist_tracks_by_playlistid": {
            "function": get_playlist_tracks_by_playlistid,
            "description": "Get all tracks from a Tidal playlist using the playlist ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_id": {
                        "type": "string",
                        "description": "ID of the playlist to get tracks from"
                    }
                },
                "required": ["playlist_id"]
            }
        },
        "tidal_get_playlist_tracks": {
            "function": get_playlist_tracks,
            "description": "Get all tracks from a Tidal playlist using the playlist name",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_name": {
                        "type": "string",
                        "description": "Name of the playlist to get tracks from"
                    }
                },
                "required": ["playlist_name"]
            }
        },
    }
    return tool_function_map 