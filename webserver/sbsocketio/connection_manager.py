import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.user_sid_map = {}
        self.sid_user_map = {}
        self.connection_data = {}

    def add_connection(self, user_id: str, sid: str, data: dict = None):
        self.user_sid_map[user_id] = sid
        self.sid_user_map[sid] = user_id
        if data:
            self.connection_data[sid] = data
        logger.info(f"Added connection: user_id={user_id}, sid={sid}")

    def remove_connection(self, sid: str):
        user_id = self.sid_user_map.pop(sid, None)
        if user_id:
            self.user_sid_map.pop(user_id, None)
            logger.info(f"Removed connection: user_id={user_id}, sid={sid}")
            return user_id
        else:
            logger.warning(f"No user_id found for sid={sid}")
            return None

    def get_sid(self, user_id: str):
        return self.user_sid_map.get(user_id)

    def get_user_id(self, sid: str):
        return self.sid_user_map.get(sid)

    def get_connection_data(self, user_id: str) -> dict:
        logger.info(f"[GET CONNECTION DATA] Getting connection data for user {user_id}")
        sid = self.user_sid_map.get(user_id)
        return self.connection_data.get(sid) if sid else None