import aiomcache
from webserver.config import settings

client = aiomcache.Client(settings.MEMCACHE_HOST, settings.MEMCACHE_PORT)

async def get_memcache_client():
    return client

async def close_client():
    client.close()