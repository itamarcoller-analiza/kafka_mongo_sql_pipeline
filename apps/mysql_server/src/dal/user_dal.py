"""Data Access Layer for users table."""

import logging

from src.db.connection import get_database

logger = logging.getLogger(__name__)


class UserDAL:

    def insert_user(self, user_id, email, phone, display_name, avatar, bio,
                    version, deleted_at, created_at, updated_at,
                    event_id, event_timestamp):
        # TODO: Implement (TASK_01)
        pass

    def soft_delete_user(self, user_id, event_id, event_timestamp):
        # TODO: Implement (TASK_01)
        pass
