"""Data Access Layer for suppliers table."""

import logging

from src.db.connection import get_database

logger = logging.getLogger(__name__)


class SupplierDAL:

    def insert_supplier(self, supplier_id, email, primary_phone,
                        contact_person_name, contact_person_title,
                        contact_person_email, contact_person_phone,
                        legal_name, dba_name,
                        street_address_1, street_address_2,
                        city, state, zip_code, country,
                        support_email, support_phone,
                        facebook_url, instagram_handle,
                        twitter_handle, linkedin_url, timezone,
                        created_at, updated_at,
                        event_id, event_timestamp):
        # TODO: Implement (TASK_02)
        pass

    def delete_supplier(self, supplier_id):
        # TODO: Implement (TASK_02)
        pass
