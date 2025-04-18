import json
import boto3
import os
import logging
from spotipy.cache_handler import CacheHandler

logger = logging.getLogger(__name__)

class SpotifySSMCacheHandler(CacheHandler):
    """
    Spotipy-compatible cache handler that stores token info in AWS SSM Parameter Store.
    Uses in-memory cache to avoid repeated reads.
    """

    def __init__(self, param_name=None, region_name=None):
        self.param_name = param_name
        self.region_name = region_name
        self._ssm = boto3.client("ssm", region_name=self.region_name)
        self._memory_token_info = None
        self._load_token_from_ssm()

    def _load_token_from_ssm(self):
        try:
            response = self._ssm.get_parameter(Name=self.param_name, WithDecryption=True)
            self._memory_token_info = json.loads(response['Parameter']['Value'])
            logger.info(f"[Spotify Cache] Loaded token from SSM: {self.param_name}")
        except self._ssm.exceptions.ParameterNotFound:
            logger.warning(f"[Spotify Cache] No token found in SSM at {self.param_name}")
            self._memory_token_info = None
        except Exception as e:
            logger.warning(f"[Spotify Cache] Failed to load token from SSM: {e}")
            self._memory_token_info = None

    def get_cached_token(self):
        return self._memory_token_info

    def save_token_to_cache(self, token_info):
        self._memory_token_info = token_info
        try:
            self._ssm.put_parameter(
                Name=self.param_name,
                Value=json.dumps(token_info),
                Type="SecureString",
                Overwrite=True
            )
            logger.info(f"[Spotify Cache] Token saved to SSM at {self.param_name}")
        except Exception as e:
            logger.warning(f"[Spotify Cache] Failed to save token to SSM: {e}")
