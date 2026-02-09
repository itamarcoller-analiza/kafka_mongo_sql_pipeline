"""Supplier events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.supplier_dal import SupplierDAL

logger = logging.getLogger(__name__)


class SupplierConsumer:

    def __init__(self):
        self._dal = SupplierDAL()

    def _parse_ts(self, ts):
        # TODO: Implement (TASK_02)
        pass

    def _handle_supplier_upsert(self, event: dict):
        """Shared handler for created and updated (both send full model)."""
        # TODO: Implement (TASK_02)
        pass

    def handle_supplier_created(self, event: dict):
        # TODO: Implement (TASK_02)
        pass

    def handle_supplier_updated(self, event: dict):
        # TODO: Implement (TASK_02)
        pass

    def handle_supplier_deleted(self, event: dict):
        # TODO: Implement (TASK_02)
        pass

    def get_handlers(self) -> dict:
        # TODO: Implement (TASK_02) - return EventType -> handler mapping
        return {}
