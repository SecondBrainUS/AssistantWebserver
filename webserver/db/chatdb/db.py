import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import CollectionInvalid
from bson.codec_options import CodecOptions
from bson.binary import UuidRepresentation
from webserver.config import settings

logger = logging.getLogger(__name__)

class MongoDBClient:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}...")
        
        # Create client with UUID representation specified
        self.client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            uuidRepresentation='standard'
        )
        
        # Get database with proper codec options
        db = self.client[settings.MONGODB_DB_NAME]
        self.db = db.with_options(
            codec_options=CodecOptions(
                uuid_representation=UuidRepresentation.STANDARD
            )
        )
        
        logger.info("MongoDB connection established.")

        # Create collections and indexes
        await self.create_collections()
        await self.create_indexes()

    async def close(self):
        if self.client:
            logger.info("Closing MongoDB connection.")
            self.client.close()

    async def get_collection(self, name: str):
        # Ensure collections also have the proper codec options
        collection = self.db[name]
        return collection.with_options(
            codec_options=CodecOptions(
                uuid_representation=UuidRepresentation.STANDARD
            )
        )

    async def create_collections(self):
        try:
            await self.db.create_collection("chats")
            await self.db.create_collection("messages")
            logger.info("Collections created successfully.")
        except CollectionInvalid:
            logger.info("Collections already exist.")

    async def create_indexes(self):
        chats = await self.get_collection("chats")
        messages = await self.get_collection("messages")

        await chats.create_index([("participant_user_ids", 1), ("last_message_at", -1)], background=True)
        await chats.create_index([("owner_user_id", 1)], background=True)
        await messages.create_index([("chat_id", 1), ("created_at", -1)], background=True)
        await messages.create_index([("user_id", 1)], background=True)
        logger.info("Indexes created successfully.")

mongodb_client = MongoDBClient() 