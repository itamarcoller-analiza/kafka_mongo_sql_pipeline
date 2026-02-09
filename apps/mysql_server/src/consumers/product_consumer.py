"""Product events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.product_dal import ProductDAL

logger = logging.getLogger(__name__)


class ProductConsumer:

    def __init__(self):
        self._dal = ProductDAL()

    def _parse_ts(self, ts):
        # TODO: Implement (TASK_04)
        pass

    def _handle_product_upsert(self, event: dict):
        """Shared handler for all events that send full product model."""
        # TODO: Implement (TASK_04)
        pass

    def handle_product_created(self, event: dict):
        # TODO: Implement (TASK_04)
        pass

    def handle_product_updated(self, event: dict):
        # TODO: Implement (TASK_04)
        pass

    def handle_product_published(self, event: dict):
        # TODO: Implement (TASK_04)
        pass

    def handle_product_discontinued(self, event: dict):
        # TODO: Implement (TASK_04)
        pass

    def handle_product_out_of_stock(self, event: dict):
        # TODO: Implement (TASK_04)
        pass

    def handle_product_restored(self, event: dict):
        # TODO: Implement (TASK_04)
        pass

    def handle_product_deleted(self, event: dict):
        # TODO: Implement (TASK_04)
        pass

    def get_handlers(self) -> dict:
        # TODO: Implement (TASK_04) - return EventType -> handler mapping
        return {}
