import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.user_sid_map = {}
        self.sid_user_map = {}

    def add_connection(self, user_id: str, sid: str):
        self.user_sid_map[user_id] = sid
        self.sid_user_map[sid] = user_id
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
