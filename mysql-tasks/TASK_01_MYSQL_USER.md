# TASK 01: User - MySQL Analytics Consumer

## 1. MISSION BRIEFING

You are building the **user analytics pipeline** - the first domain in the MySQL analytics service. When a user signs up, updates their profile, or deletes their account on the platform, a Kafka event is emitted. Your job is to catch that event, flatten the nested MongoDB user document, and store it as a flat row in MySQL.

This is the simplest domain: one table, two nested objects to flatten, and three event types to handle. Master this pattern here - you'll repeat it with increasing complexity in every subsequent task.

### What You Will Build

| Layer | File | What You Implement |
|-------|------|--------------------|
| DDL | `src/db/tables.py` | `CREATE TABLE users` with 12 columns and 2 indexes |
| DAL | `src/dal/user_dal.py` | `insert_user()` (upsert) + `soft_delete_user()` (UPDATE) |
| Consumer | `src/consumers/user_consumer.py` | 3 event handlers + timestamp parser + handler registry |

### What You Will Learn

| SQL Concept | Where You'll Use It |
|-------------|-------------------|
| `CREATE TABLE IF NOT EXISTS` | Defining the `users` table schema |
| `VARCHAR`, `INT`, `DATETIME(6)`, `TEXT` | Choosing column types for flattened data |
| `PRIMARY KEY` | `user_id VARCHAR(24)` as the row identifier |
| `INDEX` | Secondary indexes on `email` and `created_at` |
| `DEFAULT` | `version INT DEFAULT 1` |
| `INSERT ... ON DUPLICATE KEY UPDATE` | Idempotent upsert for created/updated events |
| `UPDATE ... SET ... WHERE` | Soft delete by setting `deleted_at` |
| Parameterized queries (`%s`) | Safe SQL execution via cursor |

---

## 2. BEFORE YOU START

### Prerequisites
- TASK_00 completed (environment verified, architecture understood)
- All 5 Docker containers running (`docker compose up -d`)
- You have read the four infrastructure files listed in TASK_00 Section 5

### Files You MUST Read Before Coding

Read these files in this exact order:

#### Step 1: The MongoDB User Model (understand the source data)
```
shared/models/user.py
```
This is the nested MongoDB document structure. Pay attention to:
- `ContactInfo` embedded document: `primary_email`, `additional_emails`, `phone`
- `UserProfile` embedded document: `display_name`, `avatar`, `bio`, `date_of_birth`
- Top-level fields: `password_hash`, `deleted_at`, `version`, `created_at`, `updated_at`

> **Note:** Not every MongoDB field needs a MySQL column. `password_hash` is sensitive and excluded. `additional_emails` and `date_of_birth` are low-value for analytics and excluded.

#### Step 2: The Student DAL File (understand your target)
```
apps/mysql_server/src/dal/user_dal.py
```

#### Step 3: The Student Consumer File (understand your target)
```
apps/mysql_server/src/consumers/user_consumer.py
```

#### Step 4: The Kafka Event Types
```
shared/kafka/topics.py
```
The User domain has 3 event types:
- `EventType.USER_CREATED` = `"user.created"`
- `EventType.USER_UPDATED` = `"user.updated"`
- `EventType.USER_DELETED` = `"user.deleted"`

---

## 3. SCHEMA DEEP DIVE

### The Target: `users` Table

```
users
├── user_id          VARCHAR(24)   PRIMARY KEY    ← MongoDB _id as string
├── email            VARCHAR(255)  NOT NULL       ← contact_info.primary_email
├── phone            VARCHAR(50)                  ← contact_info.phone (nullable)
├── display_name     VARCHAR(100)  NOT NULL       ← profile.display_name
├── avatar           TEXT                         ← profile.avatar (URL, can be long)
├── bio              VARCHAR(500)                 ← profile.bio (nullable)
├── version          INT           DEFAULT 1      ← optimistic locking counter
├── deleted_at       DATETIME(6)                  ← soft delete timestamp (nullable)
├── created_at       DATETIME(6)   NOT NULL       ← document creation time
├── updated_at       DATETIME(6)   NOT NULL       ← last modification time
├── event_id         VARCHAR(36)                  ← Kafka event UUID for tracing
├── event_timestamp  DATETIME(6)                  ← when the Kafka event was emitted
│
├── INDEX idx_users_email (email)                 ← fast lookup by email
└── INDEX idx_users_created (created_at)          ← fast range queries by signup date
```

### Column-by-Column Analysis

| Column | Type | Why This Type | Nullable? | Source |
|--------|------|--------------|-----------|--------|
| `user_id` | `VARCHAR(24)` | MongoDB ObjectId is always 24 hex chars | No (PK) | `event.entity_id` |
| `email` | `VARCHAR(255)` | RFC 5321 max email length | No | `data.contact_info.primary_email` |
| `phone` | `VARCHAR(50)` | International format with country code | Yes | `data.contact_info.phone` |
| `display_name` | `VARCHAR(100)` | Reasonable name length | No | `data.profile.display_name` |
| `avatar` | `TEXT` | URLs can exceed VARCHAR limits | Yes | `data.profile.avatar` |
| `bio` | `VARCHAR(500)` | Bounded user bio | Yes | `data.profile.bio` |
| `version` | `INT` | Monotonic counter | No (default 1) | `data.version` |
| `deleted_at` | `DATETIME(6)` | NULL = active, set = soft-deleted | Yes | `data.deleted_at` |
| `created_at` | `DATETIME(6)` | Microsecond precision for event ordering | No | `data.created_at` |
| `updated_at` | `DATETIME(6)` | Tracks last change | No | `data.updated_at` |
| `event_id` | `VARCHAR(36)` | UUID format (8-4-4-4-12 = 36 chars) | Yes | `event.event_id` |
| `event_timestamp` | `DATETIME(6)` | When Kafka event was emitted | Yes | `event.timestamp` |

### Index Analysis

| Index | Columns | Why |
|-------|---------|-----|
| `PRIMARY KEY` | `user_id` | Every row uniquely identified by MongoDB ObjectId |
| `idx_users_email` | `email` | Analytics queries: "find user by email", "count by email domain" |
| `idx_users_created` | `created_at` | Analytics queries: "signups per day/week/month", date range filters |

---

## 4. THE FLATTENING MAP

### MongoDB User Document -> MySQL `users` Row

```
MongoDB Document (nested)              MySQL Column (flat)
===========================            ===================

event.entity_id ─────────────────────> user_id

data.contact_info ──┐
  .primary_email ───┼────────────────> email
  .phone ───────────┘────────────────> phone

data.profile ───────┐
  .display_name ────┼────────────────> display_name
  .avatar ──────────┼────────────────> avatar
  .bio ─────────────┘────────────────> bio

data.version ────────────────────────> version
data.deleted_at ─────────────────────> deleted_at
data.created_at ─────────────────────> created_at
data.updated_at ─────────────────────> updated_at

event.event_id ──────────────────────> event_id
event.timestamp ─────────────────────> event_timestamp


NOT mapped (intentionally excluded):
  - data.password_hash         → Sensitive, not needed for analytics
  - data.contact_info.additional_emails → Low analytics value
  - data.profile.date_of_birth → Low analytics value
```

### The Event Payloads

**USER_CREATED / USER_UPDATED** (full document):
```json
{
  "event_type": "user.created",
  "event_id": "uuid-string",
  "entity_id": "507f1f77bcf86cd799439011",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": {
    "contact_info": {
      "primary_email": "jane@example.com",
      "additional_emails": [],
      "phone": "+1234567890"
    },
    "profile": {
      "display_name": "Jane Smith",
      "avatar": "https://cdn.example.com/default.jpg",
      "bio": null
    },
    "version": 1,
    "deleted_at": null,
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  }
}
```

**USER_DELETED** (minimal payload):
```json
{
  "event_type": "user.deleted",
  "event_id": "uuid-string",
  "entity_id": "507f1f77bcf86cd799439011",
  "timestamp": "2025-01-15T11:00:00Z",
  "data": {
    "user_id": "507f1f77bcf86cd799439011"
  }
}
```

---

## 5. IMPLEMENTATION EXERCISES

> **Rule:** Implement each exercise completely and verify it works before moving to the next. The layers build on each other: DDL first (table must exist), then DAL (SQL methods), then Consumer (event handlers).

---

### Exercise 5.1: Define the `users` Table (DDL)

**Concept:** `CREATE TABLE IF NOT EXISTS` with column types, PRIMARY KEY, INDEX, DEFAULT
**Difficulty:** Easy

#### Implement: Add the `users` table DDL to `TABLE_DEFINITIONS` in `src/db/tables.py`

Insert the following into the `TABLE_DEFINITIONS` list:

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id         VARCHAR(24) PRIMARY KEY,
    email           VARCHAR(255) NOT NULL,
    phone           VARCHAR(50),
    display_name    VARCHAR(100) NOT NULL,
    avatar          TEXT,
    bio             VARCHAR(500),
    version         INT DEFAULT 1,
    deleted_at      DATETIME(6),
    created_at      DATETIME(6) NOT NULL,
    updated_at      DATETIME(6) NOT NULL,
    event_id        VARCHAR(36),
    event_timestamp DATETIME(6),
    INDEX idx_users_email (email),
    INDEX idx_users_created (created_at)
)
```

#### Verify Exercise 5.1

```bash
# Restart to pick up the new DDL
docker compose restart mysql-service

# Check the table was created
docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SHOW CREATE TABLE users\G"
```

**Expected:** You should see the full CREATE TABLE output with all 12 columns and 2 indexes.

---

### Exercise 5.2: Write the DAL Methods (Raw SQL)

**Concept:** `INSERT ... ON DUPLICATE KEY UPDATE` for upsert + `UPDATE ... SET ... WHERE` for soft delete
**Difficulty:** Easy-Medium

#### Implement: `UserDAL.insert_user()` and `UserDAL.soft_delete_user()` in `src/dal/user_dal.py`

Insert the following two methods into the `UserDAL` class:

```python
def insert_user(self, user_id, email, phone, display_name, avatar, bio,
                version, deleted_at, created_at, updated_at,
                event_id, event_timestamp):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users
                (user_id, email, phone, display_name, avatar, bio,
                 version, deleted_at, created_at, updated_at,
                 event_id, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                email=VALUES(email), phone=VALUES(phone),
                display_name=VALUES(display_name), avatar=VALUES(avatar),
                bio=VALUES(bio), version=VALUES(version),
                deleted_at=VALUES(deleted_at), updated_at=VALUES(updated_at),
                event_id=VALUES(event_id), event_timestamp=VALUES(event_timestamp)
        """, (user_id, email, phone, display_name, avatar, bio,
              version, deleted_at, created_at, updated_at,
              event_id, event_timestamp))
        cursor.close()
    finally:
        conn.close()

def soft_delete_user(self, user_id, event_id, event_timestamp):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET deleted_at = NOW(6),
                event_id = %s, event_timestamp = %s
            WHERE user_id = %s
        """, (event_id, event_timestamp, user_id))
        cursor.close()
    finally:
        conn.close()
```

**Key design decisions:**
- `ON DUPLICATE KEY UPDATE` skips `user_id` (PK, immutable) and `created_at` (set once on first insert, never overwritten)
- `soft_delete_user` uses `NOW(6)` instead of a passed timestamp because the delete event payload is minimal
- `%s` parameterized queries prevent SQL injection
- `try/finally` ensures the connection is always returned to the pool

#### Verify Exercise 5.2

```bash
docker compose restart mysql-service
docker compose logs mysql-service | tail -10
# Should show "MySQL Analytics Service starting..." without import errors
```

---

### Exercise 5.3: Write the Consumer Event Handlers

**Concept:** Event dict traversal, nested field extraction, timestamp parsing, handler registry
**Difficulty:** Easy-Medium

#### Implement: All methods in `UserConsumer` in `src/consumers/user_consumer.py`

Insert the following methods into the `UserConsumer` class (which already has `__init__` with `self._dal = UserDAL()`):

```python
def _parse_ts(self, ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def _handle_user_upsert(self, event: dict):
    """Shared handler for created and updated (both send full model)."""
    data = event.get("data", {})
    contact = data.get("contact_info", {})
    profile = data.get("profile", {})

    self._dal.insert_user(
        user_id=event.get("entity_id"),
        email=contact.get("primary_email"),
        phone=contact.get("phone"),
        display_name=profile.get("display_name"),
        avatar=profile.get("avatar"),
        bio=profile.get("bio"),
        version=data.get("version", 1),
        deleted_at=self._parse_ts(data.get("deleted_at")),
        created_at=self._parse_ts(data.get("created_at")),
        updated_at=self._parse_ts(data.get("updated_at")),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )

def handle_user_created(self, event: dict):
    self._handle_user_upsert(event)
    logger.info(f"[USER_CREATED] {event['entity_id']}")

def handle_user_updated(self, event: dict):
    self._handle_user_upsert(event)
    logger.info(f"[USER_UPDATED] {event['entity_id']}")

def handle_user_deleted(self, event: dict):
    data = event.get("data", {})
    self._dal.soft_delete_user(
        user_id=data.get("user_id") or event.get("entity_id"),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )
    logger.info(f"[USER_DELETED] {event['entity_id']}")

def get_handlers(self) -> dict:
    return {
        EventType.USER_CREATED: self.handle_user_created,
        EventType.USER_UPDATED: self.handle_user_updated,
        EventType.USER_DELETED: self.handle_user_deleted,
    }
```

**Key design decisions:**
- `_handle_user_upsert` is shared between created and updated handlers - both events carry the full document, and the DAL's `ON DUPLICATE KEY UPDATE` handles the difference
- `.get("key", {})` returns an empty dict if the key is missing, so chained `.get()` calls never crash
- `_parse_ts` replaces `"Z"` with `"+00:00"` because Python's `fromisoformat` requires an explicit timezone offset
- The delete handler tries `data.get("user_id")` first, falling back to `event.get("entity_id")`

#### Verify Exercise 5.3

**Step 1: Restart the service**
```bash
docker compose restart mysql-service
```

**Step 2: Create a user via the MongoDB backend**
```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "analytics-test@example.com",
    "password": "MySecure1Pass",
    "display_name": "Analytics Test User"
  }'
```

Save the returned `id` value.

**Step 3: Check consumer logs**
```bash
docker compose logs mysql-service | grep USER_CREATED
# Expected: [USER_CREATED] <the-user-id>
```

**Step 4: Query MySQL**
```bash
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT * FROM users WHERE email = 'analytics-test@example.com'\G"
```

**Expected output:**
```
*************************** 1. row ***************************
       user_id: <24-char-hex-id>
         email: analytics-test@example.com
         phone: NULL
  display_name: Analytics Test User
        avatar: https://cdn.example.com/avatars/default.jpg
           bio: NULL
       version: 1
    deleted_at: NULL
    created_at: 2025-01-15 10:30:00.000000
    updated_at: 2025-01-15 10:30:00.000000
      event_id: <uuid>
event_timestamp: 2025-01-15 10:30:00.000000
```

**Step 5: Test update (verify upsert)**
```bash
curl -X PATCH http://localhost:8000/users/<user-id> \
  -H "Content-Type: application/json" \
  -d '{"display_name": "Updated Name", "bio": "Hello from analytics!"}'

docker compose logs mysql-service | grep USER_UPDATED

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT user_id, display_name, bio, updated_at FROM users WHERE email = 'analytics-test@example.com'\G"
# display_name should be "Updated Name", bio should be "Hello from analytics!"
# There should still be only 1 row (not 2)
```

**Step 6: Test soft delete**
```bash
curl -X DELETE http://localhost:8000/users/<user-id>

docker compose logs mysql-service | grep USER_DELETED

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT user_id, email, deleted_at FROM users WHERE email = 'analytics-test@example.com'\G"
# deleted_at should now have a timestamp (not NULL)
# The row should still exist (soft delete, not hard delete)
```

---

## 6. VERIFICATION CHECKLIST

Before moving to TASK_02, verify that ALL of the following pass:

### Table Checks
- [ ] `SHOW TABLES;` includes `users`
- [ ] `DESCRIBE users;` shows 12 columns with correct types
- [ ] `SHOW CREATE TABLE users\G` shows both indexes (`idx_users_email`, `idx_users_created`)
- [ ] `user_id` is PRIMARY KEY with `VARCHAR(24)`
- [ ] `version` has DEFAULT 1

### Functional Checks
- [ ] **Create user** via REST API -> `[USER_CREATED]` appears in mysql-service logs
- [ ] **MySQL row created** with correct email, display_name, avatar defaults
- [ ] **Update user** via REST API -> `[USER_UPDATED]` appears in logs
- [ ] **MySQL row updated** (display_name changed) without creating a duplicate row
- [ ] **`created_at` preserved** after update (not overwritten)
- [ ] **Delete user** via REST API -> `[USER_DELETED]` appears in logs
- [ ] **MySQL row soft-deleted** (`deleted_at` set to a timestamp, row still exists)

### Code Quality Checks
- [ ] All SQL uses `%s` parameterized queries (no string formatting/f-strings in SQL)
- [ ] `try/finally` pattern used in every DAL method (connection always returned to pool)
- [ ] `_parse_ts` handles None/empty gracefully (returns None)
- [ ] `_handle_user_upsert` shared between created and updated handlers (no code duplication)
- [ ] `get_handlers()` maps all 3 EventTypes

---

## 7. ADVANCED CHALLENGES

These are optional exercises that deepen your understanding.

### Challenge A: Idempotency Test

Process the same event twice and verify the table still has only one row:

```bash
# Create a user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email": "idempotent@test.com", "password": "Pass123!", "display_name": "Idempotent Test"}'

# Check row count
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT COUNT(*) as count FROM users WHERE email = 'idempotent@test.com';"
# Should be 1

# Reset consumer offset and replay all events
docker compose exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group mysql-analytics-service \
  --reset-offsets --to-earliest \
  --topic user --execute
docker compose restart mysql-service

# Wait a few seconds, then check row count again
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT COUNT(*) as count FROM users WHERE email = 'idempotent@test.com';"
# Should STILL be 1 (ON DUPLICATE KEY UPDATE handled the replay)
```

### Challenge B: The `created_at` Preservation Question

After creating and then updating a user, compare `created_at` and `updated_at`:

```sql
SELECT user_id, created_at, updated_at,
       TIMESTAMPDIFF(SECOND, created_at, updated_at) as seconds_apart
FROM users
WHERE email = 'analytics-test@example.com';
```

**Question:** Why is `created_at` excluded from the `ON DUPLICATE KEY UPDATE` clause? What would happen if you included it?

**Answer:** `created_at` is an immutable field set once on first insert. Excluding it from the UPDATE clause guarantees the original creation timestamp is preserved even when later events replay. In more complex domains (like Order), INSERT and UPDATE events may carry different timestamps, making this preservation critical for accurate analytics.

---

## 8. WHAT'S NEXT

You've completed the first domain. You now understand:
- `CREATE TABLE IF NOT EXISTS` with column types, PRIMARY KEY, INDEX, DEFAULT
- `INSERT ... ON DUPLICATE KEY UPDATE` for idempotent upserts
- `UPDATE ... SET ... WHERE` for targeted row modifications
- The connection pool pattern: `get_connection()` / `try/finally` / `conn.close()`
- Kafka event flattening: nested dict -> flat parameters -> SQL columns
- Timestamp parsing: ISO 8601 string -> Python datetime -> MySQL DATETIME(6)
- The three-step verification: Trigger -> Check Logs -> Query MySQL

**TASK 02: Supplier** will build on these concepts with:
- A much wider table (26 columns vs 12)
- Flattening from 4 nested sources (contact_info, company_info, business_address, business_info)
- A composite index (country, state, city)
- Hard DELETE instead of soft delete
- A 26-parameter INSERT statement

The three-layer pattern (DDL -> DAL -> Consumer) stays the same. The complexity grows.
