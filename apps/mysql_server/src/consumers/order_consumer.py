"""Order events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.order_dal import OrderDAL

logger = logging.getLogger(__name__)


class OrderConsumer:

    def __init__(self):
        self._dal = OrderDAL()

    def _parse_ts(self, ts):
        # TODO: Implement (TASK_07)
        pass

    def handle_order_created(self, event: dict):
        # TODO: Implement (TASK_07)
        pass

    def handle_order_cancelled(self, event: dict):
        # TODO: Implement (TASK_07)
        pass

    def get_handlers(self) -> dict:
        # TODO: Implement (TASK_07) - return EventType -> handler mapping
        return {}
