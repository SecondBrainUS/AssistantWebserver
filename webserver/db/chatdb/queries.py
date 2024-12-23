
# import logging
# from datetime import datetime
# from bson import ObjectId
# from webserver.db.chatdb.connection import db

# logger = logging.getLogger(__name__)

# async def create_chat(owner_user_id: str, participant_user_ids: list, title: str):
#     now = datetime.utcnow()
#     doc = {
#         "owner_user_id": owner_user_id,
#         "participant_user_ids": participant_user_ids,
#         "title": title or "Untitled",
#         "created_at": now,
#         "last_message_at": now
#     }
#     result = await db.chats.insert_one(doc)
#     logger.debug(f"Inserted chat with id: {result.inserted_id}")
#     return {**doc, "_id": result.inserted_id}

# async def create_message(chat_id, user_id: str, role: str, content: str, **kwargs):
#     now = datetime.utcnow()
#     msg_doc = {
#         "chat_id": chat_id,
#         "user_id": user_id,
#         "role": role,
#         "content": content,
#         "created_at": now,
#         **kwargs
#     }
#     message_result = await db.messages.insert_one(msg_doc)
#     await db.chats.update_one({"_id": ObjectId(chat_id)}, {"$set": {"last_message_at": now}})
#     logger.debug(f"Inserted message with id: {message_result.inserted_id} in chat: {chat_id}")
#     return {**msg_doc, "_id": message_result.inserted_id}

# async def get_recent_chats_for_user(user_id: str, limit: int = 10):
#     cursor = db.chats.find({"participant_user_ids": user_id}).sort("last_message_at", -1).limit(limit)
#     return await cursor.to_list(length=limit)

# async def get_recent_messages_for_chat(chat_id, limit: int = 20):
#     cursor = db.messages.find({"chat_id": ObjectId(chat_id)}).sort("created_at", -1).limit(limit)
#     return await cursor.to_list(length=limit)
