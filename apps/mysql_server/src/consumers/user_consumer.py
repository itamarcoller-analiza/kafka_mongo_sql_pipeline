"""User events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.user_dal import UserDAL

logger = logging.getLogger(__name__)


class UserConsumer:

    def __init__(self):
        self._dal = UserDAL()

    def _parse_ts(self, ts):
        # TODO: Implement (TASK_01)
        pass

    def _handle_user_upsert(self, event: dict):
        """Shared handler for created and updated (both send full model)."""
        # TODO: Implement (TASK_01)
        pass

    def handle_user_created(self, event: dict):
        # TODO: Implement (TASK_01)
        pass

    def handle_user_updated(self, event: dict):
        # TODO: Implement (TASK_01)
        pass

    def handle_user_deleted(self, event: dict):
        # TODO: Implement (TASK_01)
        pass

    def get_handlers(self) -> dict:
        # TODO: Implement (TASK_01) - return EventType -> handler mapping
        return {}
