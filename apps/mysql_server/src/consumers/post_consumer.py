"""Post events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.post_dal import PostDAL

logger = logging.getLogger(__name__)


class PostConsumer:

    def __init__(self):
        self._dal = PostDAL()

    def _parse_ts(self, ts):
        # TODO: Implement (TASK_05)
        pass

    def _handle_post_upsert(self, event: dict):
        """Shared handler for all events that send full post model."""
        # TODO: Implement (TASK_05)
        pass

    def handle_post_created(self, event: dict):
        # TODO: Implement (TASK_05)
        pass

    def handle_post_updated(self, event: dict):
        # TODO: Implement (TASK_05)
        pass

    def handle_post_published(self, event: dict):
        # TODO: Implement (TASK_05)
        pass

    def handle_post_deleted(self, event: dict):
        # TODO: Implement (TASK_05)
        pass

    def get_handlers(self) -> dict:
        # TODO: Implement (TASK_05) - return EventType -> handler mapping
        return {}
