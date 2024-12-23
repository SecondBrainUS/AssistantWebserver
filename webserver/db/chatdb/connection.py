import logging
from webserver.db.chatdb.db import mongodb_client

logger = logging.getLogger(__name__)

async def get_chats_collection():
    return await mongodb_client.get_collection("chats")

async def get_messages_collection():
    return await mongodb_client.get_collection("messages")

async def create_indexes():
    chats = await get_chats_collection()
    messages = await get_messages_collection()

    await chats.create_index([("participant_user_ids", 1), ("last_message_at", -1)], background=True)
    await chats.create_index([("owner_user_id", 1)], background=True)
    await messages.create_index([("chat_id", 1), ("created_at", -1)], background=True)
    await messages.create_index([("user_id", 1)], background=True)