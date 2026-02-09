# TASK 02: Supplier - MySQL Analytics Consumer

## 1. MISSION BRIEFING

You are building the **supplier analytics pipeline**. Suppliers are the vendors who list products on the platform. Their MongoDB documents are deeply nested - contact info, company details, business address, and social links are all stored as embedded objects. Your job is to flatten all of that into a single 26-column relational row.

This task introduces two new challenges compared to User:
- **Wide tables** - 26 columns sourced from 4 different nested objects
- **Hard DELETE** - suppliers are permanently removed, not soft-deleted

### What You Will Build

| Layer | File | What You Implement |
|-------|------|--------------------|
| DDL | `src/db/tables.py` | `CREATE TABLE suppliers` with 26 columns and 3 indexes |
| DAL | `src/dal/supplier_dal.py` | `insert_supplier()` (26-param upsert) + `delete_supplier()` (hard delete) |
| Consumer | `src/consumers/supplier_consumer.py` | 3 event handlers with 4-source flattening |

### What You Will Learn

| SQL Concept | Where You'll Use It |
|-------------|-------------------|
| Wide table design (25+ columns) | Flattening deeply nested docs into a single table |
| Composite INDEX | `INDEX (country, state, city)` for geographic queries |
| Hard DELETE | `DELETE FROM suppliers WHERE supplier_id = %s` |
| 26-parameter INSERT | Large parameterized query with ON DUPLICATE KEY UPDATE |
| Multi-source flattening | Extracting from 4 nested objects in one consumer handler |

---

## 2. BEFORE YOU START

### Prerequisites
- TASK_01 completed (User DDL + DAL + Consumer working)
- All 5 Docker containers running

### Files You MUST Read Before Coding

#### Step 1: The MongoDB Supplier Model
```
shared/models/supplier.py
```
Pay attention to the nesting depth:
- `ContactInfo` → `primary_email`, `primary_phone`, `contact_person_name`, `contact_person_title`, `contact_person_email`, `contact_person_phone`
- `CompanyInfo` → `legal_name`, `dba_name`, and embedded `CompanyAddress` → `street_address_1`, `street_address_2`, `city`, `state`, `zip_code`, `country`
- `BusinessInfo` → `support_email`, `support_phone`, `facebook_url`, `instagram_handle`, `twitter_handle`, `linkedin_url`, `timezone`

#### Step 2: The Student Files
```
apps/mysql_server/src/dal/supplier_dal.py
apps/mysql_server/src/consumers/supplier_consumer.py
```

#### Step 3: The Kafka Event Types
```
shared/kafka/topics.py
```
The Supplier domain has 3 event types:
- `EventType.SUPPLIER_CREATED` = `"supplier.created"`
- `EventType.SUPPLIER_UPDATED` = `"supplier.updated"`
- `EventType.SUPPLIER_DELETED` = `"supplier.deleted"`

---

## 3. SCHEMA DEEP DIVE

### The Target: `suppliers` Table

```
suppliers
├── supplier_id             VARCHAR(24)   PRIMARY KEY
├── email                   VARCHAR(255)  NOT NULL       ← contact_info.primary_email
├── primary_phone           VARCHAR(50)   NOT NULL       ← contact_info.primary_phone
├── contact_person_name     VARCHAR(200)                 ← contact_info.contact_person_name
├── contact_person_title    VARCHAR(200)                 ← contact_info.contact_person_title
├── contact_person_email    VARCHAR(255)                 ← contact_info.contact_person_email
├── contact_person_phone    VARCHAR(50)                  ← contact_info.contact_person_phone
├── legal_name              VARCHAR(200)  NOT NULL       ← company_info.legal_name
├── dba_name                VARCHAR(200)                 ← company_info.dba_name
├── street_address_1        VARCHAR(200)                 ← company_info.business_address.street_address_1
├── street_address_2        VARCHAR(200)                 ← company_info.business_address.street_address_2
├── city                    VARCHAR(100)                 ← company_info.business_address.city
├── state                   VARCHAR(100)                 ← company_info.business_address.state
├── zip_code                VARCHAR(20)                  ← company_info.business_address.zip_code
├── country                 VARCHAR(2)                   ← company_info.business_address.country
├── support_email           VARCHAR(255)                 ← business_info.support_email
├── support_phone           VARCHAR(50)                  ← business_info.support_phone
├── facebook_url            TEXT                         ← business_info.facebook_url
├── instagram_handle        VARCHAR(100)                 ← business_info.instagram_handle
├── twitter_handle          VARCHAR(100)                 ← business_info.twitter_handle
├── linkedin_url            TEXT                         ← business_info.linkedin_url
├── timezone                VARCHAR(50)                  ← business_info.timezone
├── created_at              DATETIME(6)   NOT NULL
├── updated_at              DATETIME(6)   NOT NULL
├── event_id                VARCHAR(36)
├── event_timestamp         DATETIME(6)
│
├── INDEX idx_suppliers_email (email)
├── INDEX idx_suppliers_legal_name (legal_name)
└── INDEX idx_suppliers_country (country, state, city)   ← COMPOSITE INDEX
```

### Composite Index Explained

`INDEX idx_suppliers_country (country, state, city)` is a **composite (multi-column) index**. It optimizes queries that filter by:
- `WHERE country = 'US'` (uses the index - leftmost prefix)
- `WHERE country = 'US' AND state = 'CA'` (uses the index)
- `WHERE country = 'US' AND state = 'CA' AND city = 'LA'` (uses the full index)

It does **not** optimize:
- `WHERE city = 'LA'` (skips the leftmost prefix - no index benefit)
- `WHERE state = 'CA'` (skips the leftmost prefix)

This is the **leftmost prefix rule** of composite indexes.

---

## 4. THE FLATTENING MAP

### MongoDB Supplier Document -> MySQL `suppliers` Row

```
MongoDB Document (nested)                    MySQL Column (flat)
===========================                  ===================

event.entity_id ───────────────────────────> supplier_id

data.contact_info ──────┐
  .primary_email ───────┼─────────────────> email
  .primary_phone ───────┼─────────────────> primary_phone
  .contact_person_name ─┼─────────────────> contact_person_name
  .contact_person_title ┼─────────────────> contact_person_title
  .contact_person_email ┼─────────────────> contact_person_email
  .contact_person_phone ┘─────────────────> contact_person_phone

data.company_info ──────┐
  .legal_name ──────────┼─────────────────> legal_name
  .dba_name ────────────┘─────────────────> dba_name

data.company_info.business_address ──┐
  .street_address_1 ────────────────┼────> street_address_1
  .street_address_2 ────────────────┼────> street_address_2
  .city ────────────────────────────┼────> city
  .state ───────────────────────────┼────> state
  .zip_code ────────────────────────┼────> zip_code
  .country ─────────────────────────┘────> country

data.business_info ─────┐
  .support_email ───────┼─────────────────> support_email
  .support_phone ───────┼─────────────────> support_phone
  .facebook_url ────────┼─────────────────> facebook_url
  .instagram_handle ────┼─────────────────> instagram_handle
  .twitter_handle ──────┼─────────────────> twitter_handle
  .linkedin_url ────────┼─────────────────> linkedin_url
  .timezone ────────────┘─────────────────> timezone

data.created_at ───────────────────────────> created_at
data.updated_at ───────────────────────────> updated_at
event.event_id ────────────────────────────> event_id
event.timestamp ───────────────────────────> event_timestamp
```

Note the **4 extraction sources** in the consumer:
1. `contact = data.get("contact_info", {})` — 6 fields
2. `company = data.get("company_info", {})` — 2 fields
3. `address = company.get("business_address", {})` — 6 fields (nested inside company!)
4. `biz = data.get("business_info", {})` — 7 fields

### The Event Payloads

**SUPPLIER_CREATED / SUPPLIER_UPDATED** (full document):
```json
{
  "event_type": "supplier.created",
  "event_id": "uuid-string",
  "entity_id": "60a7b2c3d4e5f6a7b8c9d0e1",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": {
    "contact_info": {
      "primary_email": "supplier@example.com",
      "primary_phone": "+1-555-0100",
      "contact_person_name": "John Doe",
      "contact_person_title": "Sales Manager",
      "contact_person_email": "john@example.com",
      "contact_person_phone": "+1-555-0101"
    },
    "company_info": {
      "legal_name": "Acme Corp LLC",
      "dba_name": "Acme Crafts",
      "business_address": {
        "street_address_1": "123 Main St",
        "street_address_2": "Suite 100",
        "city": "Los Angeles",
        "state": "CA",
        "zip_code": "90001",
        "country": "US"
      }
    },
    "business_info": {
      "support_email": "support@acme.com",
      "support_phone": "+1-555-0199",
      "facebook_url": "https://facebook.com/acme",
      "instagram_handle": "@acme_crafts",
      "twitter_handle": "@acme",
      "linkedin_url": "https://linkedin.com/company/acme",
      "timezone": "America/Los_Angeles"
    },
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  }
}
```

**SUPPLIER_DELETED** (minimal payload):
```json
{
  "event_type": "supplier.deleted",
  "event_id": "uuid-string",
  "entity_id": "60a7b2c3d4e5f6a7b8c9d0e1",
  "timestamp": "2025-01-15T11:00:00Z",
  "data": {
    "supplier_id": "60a7b2c3d4e5f6a7b8c9d0e1"
  }
}
```

---

## 5. IMPLEMENTATION EXERCISES

---

### Exercise 5.1: Define the `suppliers` Table (DDL)

**Concept:** Wide table (26 columns), composite index, NOT NULL on business-critical fields
**Difficulty:** Medium

#### Implement: Add the `suppliers` table DDL to `TABLE_DEFINITIONS` in `src/db/tables.py`

Append this after the `users` table definition:

```sql
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id             VARCHAR(24) PRIMARY KEY,
    email                   VARCHAR(255) NOT NULL,
    primary_phone           VARCHAR(50) NOT NULL,
    contact_person_name     VARCHAR(200),
    contact_person_title    VARCHAR(200),
    contact_person_email    VARCHAR(255),
    contact_person_phone    VARCHAR(50),
    legal_name              VARCHAR(200) NOT NULL,
    dba_name                VARCHAR(200),
    street_address_1        VARCHAR(200),
    street_address_2        VARCHAR(200),
    city                    VARCHAR(100),
    state                   VARCHAR(100),
    zip_code                VARCHAR(20),
    country                 VARCHAR(2),
    support_email           VARCHAR(255),
    support_phone           VARCHAR(50),
    facebook_url            TEXT,
    instagram_handle        VARCHAR(100),
    twitter_handle          VARCHAR(100),
    linkedin_url            TEXT,
    timezone                VARCHAR(50),
    created_at              DATETIME(6) NOT NULL,
    updated_at              DATETIME(6) NOT NULL,
    event_id                VARCHAR(36),
    event_timestamp         DATETIME(6),
    INDEX idx_suppliers_email (email),
    INDEX idx_suppliers_legal_name (legal_name),
    INDEX idx_suppliers_country (country, state, city)
)
```

**Key design decisions:**
- `country VARCHAR(2)` — ISO 3166-1 alpha-2 codes are always 2 characters
- `facebook_url` and `linkedin_url` use `TEXT` — URLs can be arbitrarily long
- `instagram_handle` and `twitter_handle` use `VARCHAR(100)` — handle lengths are bounded
- The composite index `(country, state, city)` follows the **most-selective-last** pattern for geographic drill-down queries

#### Verify Exercise 5.1

```bash
docker compose restart mysql-service

docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SHOW CREATE TABLE suppliers\G"
```

**Expected:** 26 columns, 3 indexes (plus the implicit PRIMARY KEY index).

---

### Exercise 5.2: Write the DAL Methods (Raw SQL)

**Concept:** 26-parameter INSERT ON DUPLICATE KEY UPDATE + hard DELETE
**Difficulty:** Medium

#### Implement: `SupplierDAL.insert_supplier()` and `SupplierDAL.delete_supplier()` in `src/dal/supplier_dal.py`

Insert the following two methods into the `SupplierDAL` class:

```python
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
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO suppliers
                (supplier_id, email, primary_phone,
                 contact_person_name, contact_person_title,
                 contact_person_email, contact_person_phone,
                 legal_name, dba_name,
                 street_address_1, street_address_2,
                 city, state, zip_code, country,
                 support_email, support_phone,
                 facebook_url, instagram_handle,
                 twitter_handle, linkedin_url, timezone,
                 created_at, updated_at,
                 event_id, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                email=VALUES(email), primary_phone=VALUES(primary_phone),
                contact_person_name=VALUES(contact_person_name),
                contact_person_title=VALUES(contact_person_title),
                contact_person_email=VALUES(contact_person_email),
                contact_person_phone=VALUES(contact_person_phone),
                legal_name=VALUES(legal_name), dba_name=VALUES(dba_name),
                street_address_1=VALUES(street_address_1),
                street_address_2=VALUES(street_address_2),
                city=VALUES(city), state=VALUES(state),
                zip_code=VALUES(zip_code), country=VALUES(country),
                support_email=VALUES(support_email),
                support_phone=VALUES(support_phone),
                facebook_url=VALUES(facebook_url),
                instagram_handle=VALUES(instagram_handle),
                twitter_handle=VALUES(twitter_handle),
                linkedin_url=VALUES(linkedin_url),
                timezone=VALUES(timezone),
                updated_at=VALUES(updated_at),
                event_id=VALUES(event_id),
                event_timestamp=VALUES(event_timestamp)
        """, (supplier_id, email, primary_phone,
              contact_person_name, contact_person_title,
              contact_person_email, contact_person_phone,
              legal_name, dba_name,
              street_address_1, street_address_2,
              city, state, zip_code, country,
              support_email, support_phone,
              facebook_url, instagram_handle,
              twitter_handle, linkedin_url, timezone,
              created_at, updated_at,
              event_id, event_timestamp))
        cursor.close()
    finally:
        conn.close()

def delete_supplier(self, supplier_id):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM suppliers WHERE supplier_id = %s",
                       (supplier_id,))
        cursor.close()
    finally:
        conn.close()
```

**Key design decisions:**
- Same `ON DUPLICATE KEY UPDATE` pattern as User, but skips `supplier_id` (PK) and `created_at` (immutable)
- 26 `%s` placeholders in VALUES — count carefully, a mismatch causes a runtime error
- `delete_supplier` uses **hard DELETE** (not soft delete like User). The row is permanently removed from MySQL when the supplier is deleted from MongoDB
- The single-tuple parameter `(supplier_id,)` needs a trailing comma — `(supplier_id)` without the comma is just parentheses around a value, not a tuple

#### Verify Exercise 5.2

```bash
docker compose restart mysql-service
docker compose logs mysql-service | tail -10
# No import errors
```

---

### Exercise 5.3: Write the Consumer Event Handlers

**Concept:** 4-source flattening (contact_info, company_info, business_address, business_info)
**Difficulty:** Medium

#### Implement: All methods in `SupplierConsumer` in `src/consumers/supplier_consumer.py`

Insert the following methods into the `SupplierConsumer` class:

```python
def _parse_ts(self, ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def _handle_supplier_upsert(self, event: dict):
    """Shared handler for created and updated (both send full model)."""
    data = event.get("data", {})
    contact = data.get("contact_info", {})
    company = data.get("company_info", {})
    address = company.get("business_address", {})
    biz = data.get("business_info", {})

    self._dal.insert_supplier(
        supplier_id=event.get("entity_id"),
        email=contact.get("primary_email"),
        primary_phone=contact.get("primary_phone"),
        contact_person_name=contact.get("contact_person_name"),
        contact_person_title=contact.get("contact_person_title"),
        contact_person_email=contact.get("contact_person_email"),
        contact_person_phone=contact.get("contact_person_phone"),
        legal_name=company.get("legal_name"),
        dba_name=company.get("dba_name"),
        street_address_1=address.get("street_address_1"),
        street_address_2=address.get("street_address_2"),
        city=address.get("city"),
        state=address.get("state"),
        zip_code=address.get("zip_code"),
        country=address.get("country"),
        support_email=biz.get("support_email"),
        support_phone=biz.get("support_phone"),
        facebook_url=biz.get("facebook_url"),
        instagram_handle=biz.get("instagram_handle"),
        twitter_handle=biz.get("twitter_handle"),
        linkedin_url=biz.get("linkedin_url"),
        timezone=biz.get("timezone"),
        created_at=self._parse_ts(data.get("created_at")),
        updated_at=self._parse_ts(data.get("updated_at")),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )

def handle_supplier_created(self, event: dict):
    self._handle_supplier_upsert(event)
    logger.info(f"[SUPPLIER_CREATED] {event['entity_id']}")

def handle_supplier_updated(self, event: dict):
    self._handle_supplier_upsert(event)
    logger.info(f"[SUPPLIER_UPDATED] {event['entity_id']}")

def handle_supplier_deleted(self, event: dict):
    data = event.get("data", {})
    self._dal.delete_supplier(
        supplier_id=data.get("supplier_id") or event.get("entity_id"),
    )
    logger.info(f"[SUPPLIER_DELETED] {event['entity_id']}")

def get_handlers(self) -> dict:
    return {
        EventType.SUPPLIER_CREATED: self.handle_supplier_created,
        EventType.SUPPLIER_UPDATED: self.handle_supplier_updated,
        EventType.SUPPLIER_DELETED: self.handle_supplier_deleted,
    }
```

**Key design decisions:**
- `address = company.get("business_address", {})` — address is nested **inside** company_info, not at the top level of data. This is the 3-level-deep extraction
- `legal_name` comes from `company` (not `contact`), while `primary_phone` comes from `contact` (not `company`) — pay attention to which source each field comes from
- The delete handler calls `delete_supplier` (hard delete), not a soft delete method. The row is permanently removed from MySQL

#### Verify Exercise 5.3

**Step 1: Restart the service**
```bash
docker compose restart mysql-service
```

**Step 2: Create a supplier**
```bash
curl -X POST http://localhost:8000/suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "email": "analytics-supplier@example.com",
    "password": "SupplierPass1!",
    "primary_phone": "+1-555-0100",
    "legal_name": "Analytics Test Corp",
    "street_address_1": "123 Test Blvd",
    "city": "Los Angeles",
    "state": "CA",
    "zip_code": "90001",
    "country": "US"
  }'
```

Save the returned `id` value.

**Step 3: Check consumer logs**
```bash
docker compose logs mysql-service | grep SUPPLIER_CREATED
```

**Step 4: Query MySQL**
```bash
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT supplier_id, email, legal_name, city, state, country FROM suppliers\G"
```

**Expected:** Row with `email=analytics-supplier@example.com`, `legal_name=Analytics Test Corp`, `city=Los Angeles`, `state=CA`, `country=US`.

**Step 5: Test the composite index**
```bash
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "EXPLAIN SELECT * FROM suppliers WHERE country = 'US' AND state = 'CA'\G"
# The 'key' field should show idx_suppliers_country
```

**Step 6: Test hard delete**
```bash
curl -X DELETE http://localhost:8000/suppliers/<supplier-id>

docker compose logs mysql-service | grep SUPPLIER_DELETED

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT COUNT(*) as count FROM suppliers WHERE supplier_id = '<supplier-id>';"
# Should be 0 — the row is permanently gone (hard delete, not soft delete)
```

---

## 6. VERIFICATION CHECKLIST

### Table Checks
- [ ] `SHOW TABLES;` includes `suppliers`
- [ ] `DESCRIBE suppliers;` shows 26 columns
- [ ] 3 indexes present: `idx_suppliers_email`, `idx_suppliers_legal_name`, `idx_suppliers_country`
- [ ] Composite index is `(country, state, city)` in that order

### Functional Checks
- [ ] **Create supplier** -> `[SUPPLIER_CREATED]` in logs -> row appears in MySQL with all fields
- [ ] **Update supplier** -> `[SUPPLIER_UPDATED]` in logs -> row updated, no duplicate
- [ ] **`created_at` preserved** after update
- [ ] **Delete supplier** -> `[SUPPLIER_DELETED]` in logs -> row **permanently removed** (COUNT = 0)

### Code Quality Checks
- [ ] 26 `%s` placeholders match 26 parameters in the tuple
- [ ] `address` extracted from `company` (not from `data` directly)
- [ ] Hard DELETE used (not soft delete)
- [ ] `try/finally` on every DAL method
- [ ] `get_handlers()` maps all 3 EventTypes

---

## 7. ADVANCED CHALLENGES

### Challenge A: Composite Index Leftmost Prefix

Test the leftmost prefix rule:

```sql
-- Uses the composite index (leftmost prefix: country)
EXPLAIN SELECT * FROM suppliers WHERE country = 'US'\G

-- Uses the composite index (prefix: country + state)
EXPLAIN SELECT * FROM suppliers WHERE country = 'US' AND state = 'CA'\G

-- Does NOT use the composite index (skips country)
EXPLAIN SELECT * FROM suppliers WHERE city = 'Los Angeles'\G

-- Does NOT use the composite index (skips country)
EXPLAIN SELECT * FROM suppliers WHERE state = 'CA'\G
```

Compare the `key` field in each EXPLAIN output. The first two should show `idx_suppliers_country`. The last two should show `NULL` (full table scan).

### Challenge B: Hard Delete vs Soft Delete

Compare the supplier delete (hard) with the user delete (soft):

```sql
-- After deleting a user: row still exists, deleted_at is set
SELECT user_id, deleted_at FROM users WHERE user_id = '<deleted-user-id>';

-- After deleting a supplier: row is gone
SELECT supplier_id FROM suppliers WHERE supplier_id = '<deleted-supplier-id>';
```

**Question:** When would you choose hard delete over soft delete?

**Answer:** Hard delete is appropriate when: (1) there's no audit trail requirement, (2) no other tables reference the row with foreign keys that need preservation, and (3) you want to reclaim storage. Soft delete is preferred when you need recovery, audit trails, or referential integrity. Suppliers use hard delete because the analytics DB is a derived replica - the source of truth is MongoDB, so recoverability isn't needed here.

---

## 8. WHAT'S NEXT

You've now handled two single-table domains. You understand:
- Wide table design with 25+ columns
- Multi-source flattening (4 nested objects -> 1 flat row)
- Composite indexes and the leftmost prefix rule
- Hard DELETE vs soft delete

**TASK 04: Product** introduces a fundamentally new challenge:
- **Two tables** - `products` (parent) + `product_variants` (child)
- **FOREIGN KEY ON DELETE CASCADE** - deleting a product auto-deletes its variants
- **AUTO_INCREMENT** surrogate key on the child table
- **UNIQUE KEY** composite constraint `(product_id, variant_key)`
- **JSON column** for variant attributes
- **Replace pattern** (DELETE + INSERT) for updating child rows
- **7 event types** (created, updated, published, discontinued, out_of_stock, restored, deleted)

The three-layer pattern stays the same, but now you're managing two related tables.
