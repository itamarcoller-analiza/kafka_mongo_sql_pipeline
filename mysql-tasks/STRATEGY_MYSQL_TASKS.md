# MySQL Analytics Consumer - Task Strategy

## Philosophy & Core Idea

Students receive a **fully scaffolded MySQL Analytics Service** with:
- **Connection pool** (complete) - `src/db/connection.py` manages a MySQL connection pool
- **Kafka framework** (complete) - `src/kafka/consumer.py` handles message polling, routing, and shutdown
- **Bootstrap** (complete) - `main.py` wires everything together
- **Tables** (EMPTY) - `src/db/tables.py` has an empty `TABLE_DEFINITIONS` list
- **DALs** (EMPTY SHELLS) - `src/dal/*_dal.py` files have class definitions only
- **Consumers** (EMPTY SHELLS) - `src/consumers/*_consumer.py` files have class definitions only

Students implement **three layers per domain**: DDL, DAL, and Consumer.

> **The student never touches `connection.py`, `consumer.py`, or `main.py`. They ONLY write CREATE TABLE statements, raw SQL methods, and event handler logic.**

---

## How The MDs Work

### Each MD = One Domain (Table + DAL + Consumer)

```
mysql-tasks/
├── STRATEGY_MYSQL_TASKS.md          <- This file (meta-strategy)
├── TASK_00_MYSQL_SETUP.md           <- Environment + architecture primer
├── TASK_01_MYSQL_USER.md            <- User table + DAL + Consumer
├── TASK_02_MYSQL_SUPPLIER.md        <- Supplier table + DAL + Consumer
├── TASK_04_MYSQL_PRODUCT.md         <- Product + Variants (parent/child tables)
├── TASK_05_MYSQL_POST.md            <- Post table + DAL + Consumer
└── TASK_07_MYSQL_ORDER.md           <- Order + Items (most complex)
```

### Strict Ordering - Each MD Unlocks The Next

```
TASK_01 (User)
   └-> TASK_02 (Supplier)       <- Same pattern, bigger table
         ├-> TASK_04 (Product)   <- Parent/child tables, FK CASCADE
         └-> TASK_05 (Post)      <- JSON columns, DOUBLE type
               └-> TASK_07 (Order) <- Batch inserts, selective upsert
```

Students MUST complete earlier tasks before later ones because:
- SQL concepts build incrementally (single table -> parent/child -> batch inserts)
- The three-layer pattern (DDL -> DAL -> Consumer) repeats but grows in complexity
- Later domains reference patterns established in earlier ones

---

## The Three-Layer Pattern

Every domain task follows the same implementation flow:

```
Layer 1: DDL (CREATE TABLE)
   │      Define the schema in src/db/tables.py
   │      New concepts: column types, indexes, constraints
   │
   ▼
Layer 2: DAL (Raw SQL Methods)
   │      Write INSERT/UPDATE/DELETE in src/dal/*_dal.py
   │      New concepts: ON DUPLICATE KEY UPDATE, parameterized queries
   │
   ▼
Layer 3: Consumer (Event Handlers)
          Flatten MongoDB docs -> call DAL in src/consumers/*_consumer.py
          New concepts: nested dict traversal, timestamp parsing
```

### What This Teaches

| Layer | Skill | Real-World Parallel |
|-------|-------|-------------------|
| DDL | Schema design: types, indexes, constraints | Database migrations |
| DAL | Parameterized SQL, upsert patterns, connection management | Repository pattern |
| Consumer | Event-driven architecture, document flattening, data transformation | ETL / CDC pipelines |

---

## MD Template (Every MD follows this structure)

```markdown
# TASK_XX: [Domain Name] - MySQL Analytics Consumer

## 1. MISSION BRIEFING
- What this entity does in the analytics pipeline
- Why relational storage matters for this domain
- What the student will learn (SQL concepts)

## 2. BEFORE YOU START
- Prerequisites (which previous tasks must be complete)
- Files to read before coding:
  - tables.py (understand existing DDL)
  - connection.py (understand the pool)
  - consumer.py (understand the Kafka framework)
  - The MongoDB model (understand what gets flattened)

## 3. SCHEMA DEEP DIVE
- Annotated walkthrough of the CREATE TABLE statement
- Column-by-column explanation of types and constraints
- Index analysis: what queries are optimized and why

## 4. THE FLATTENING MAP
- MongoDB document structure (nested) -> MySQL columns (flat)
- Visual mapping showing which nested field maps to which column
- Data type conversions (ObjectId -> VARCHAR(24), datetime -> DATETIME(6))

## 5. IMPLEMENTATION EXERCISES (ordered: DDL -> DAL -> Consumer)

### Exercise 5.1: [DDL] - CREATE TABLE
### Exercise 5.2: [DAL] - SQL Methods
### Exercise 5.3: [Consumer] - Event Handlers

## 6. VERIFICATION CHECKLIST
- [ ] Table created (SHOW CREATE TABLE)
- [ ] Consumer processes events (docker compose logs)
- [ ] Data correct (SELECT queries)

## 7. ADVANCED CHALLENGES (optional)
- EXPLAIN query analysis
- Edge cases and idempotency
- Performance considerations

## 8. WHAT'S NEXT
- Points to next task
```

---

## SQL Concept Progression Map

Each task introduces NEW SQL concepts while reinforcing previous ones.

### TASK_01: User
**New Concepts:**
| Concept | Layer | What They Learn |
|---------|-------|----------------|
| CREATE TABLE with types | DDL | VARCHAR, INT, DATETIME(6), TEXT, DEFAULT |
| PRIMARY KEY | DDL | VARCHAR(24) PK (MongoDB ObjectId as string) |
| INDEX | DDL | Secondary indexes on email, created_at |
| INSERT ... ON DUPLICATE KEY UPDATE | DAL | Upsert pattern for idempotent event processing |
| UPDATE with WHERE | DAL | Soft delete via UPDATE (not DELETE) |
| Event dict traversal | Consumer | Extract nested fields from Kafka event payload |

**Reinforced:** None (this is the foundation)

---

### TASK_02: Supplier
**New Concepts:**
| Concept | Layer | What They Learn |
|---------|-------|----------------|
| Wide tables (25+ columns) | DDL | Flattening deeply nested docs into many columns |
| Composite index | DDL | `INDEX (country, state, city)` for geographic queries |
| 26-parameter INSERT | DAL | Large parameterized queries |
| Hard DELETE | DAL | Permanent removal (contrast with User soft delete) |
| Multi-source flattening | Consumer | Extracting from 4 nested objects (contact, company, address, business) |

**Reinforced:** CREATE TABLE, PRIMARY KEY, INDEX, ON DUPLICATE KEY UPDATE

---

### TASK_04: Product
**New Concepts:**
| Concept | Layer | What They Learn |
|---------|-------|----------------|
| Parent/child tables | DDL | Two related tables (products + product_variants) |
| FOREIGN KEY ON DELETE CASCADE | DDL | Referential integrity with automatic child cleanup |
| AUTO_INCREMENT | DDL | Surrogate key on child table |
| UNIQUE KEY (composite) | DDL | `UNIQUE (product_id, variant_key)` |
| JSON column | DDL | `attributes_json JSON` for semi-structured data |
| Replace pattern (DELETE + INSERT) | DAL | Replace child rows by deleting then inserting |
| Dict iteration | Consumer | Iterating `variants` dict keys to build child rows |

**Reinforced:** All previous concepts

---

### TASK_05: Post
**New Concepts:**
| Concept | Layer | What They Learn |
|---------|-------|----------------|
| JSON column for arrays | DDL | `media_json JSON` storing serialized media list |
| DOUBLE type | DDL | `engagement_rate DOUBLE` for floating-point metrics |
| Complex upsert (26 params) | DAL | Large ON DUPLICATE KEY UPDATE with selective columns |
| Compound indexes | DDL | 4 indexes for different query patterns |
| `json.dumps()` in consumer | Consumer | Serializing Python lists to JSON strings for MySQL |
| Link preview flattening | Consumer | Optional nested object -> multiple flat columns |

**Reinforced:** All previous concepts

---

### TASK_07: Order
**New Concepts:**
| Concept | Layer | What They Learn |
|---------|-------|----------------|
| UNIQUE KEY on business field | DDL | `UNIQUE (order_number)` for natural key |
| Selective ON DUPLICATE KEY UPDATE | DAL | Only update status/timestamps, preserve immutable fields |
| Batch INSERT in loop | DAL | Insert multiple child rows (order_items) |
| Composite UNIQUE on child | DDL | `UNIQUE (order_id, item_id)` |
| Multi-table writes | Consumer | Insert parent (order) + children (items) in one handler |
| Product snapshot flattening | Consumer | Nested `product_snapshot` inside each item |
| Cancel by business key | DAL | UPDATE WHERE order_number (not PK) |

**Reinforced:** Everything (this is the capstone)

---

## Difficulty Curve

```
Difficulty
    |
    |                                          +-- TASK_07 (Orders+Items)
    |                                     +----'
    |                                +----' TASK_05 (Posts/JSON)
    |                           +----'
    |                      +----' TASK_04 (Products/Variants)
    |                 +----'
    |            +----' TASK_02 (Supplier/Wide Table)
    |       +----'
    |  +----' TASK_01 (User/Basics)
    |--' TASK_00 (Setup)
    +------------------------------------------------------- Time
```

### Per-Task Breakdown:
| Task | Exercises | Difficulty | Key Challenge |
|------|-----------|------------|---------------|
| 00 - Setup | 0 | N/A | Understanding the architecture |
| 01 - User | 3 | Easy | First time writing DDL + DAL + Consumer |
| 02 - Supplier | 3 | Medium | 25-column table, 4-source flattening |
| 04 - Product | 4 | Hard | Parent/child tables, FK CASCADE, replace pattern |
| 05 - Post | 3 | Medium-High | JSON columns, DOUBLE, 26-param upsert |
| 07 - Order | 4 | Very High | Batch inserts, selective upsert, multi-table |

---

## How Students Use The MDs

### Workflow Per Task

```
1. READ the MD
   |-- Understand the domain and flattening map
   |-- Read the MongoDB model (what the event payload looks like)
   |-- Read tables.py, the DAL file, and the consumer file
   '-- Understand the three-layer pattern for this domain

2. IMPLEMENT exercises in order (DDL -> DAL -> Consumer)
   |-- Exercise 5.1: CREATE TABLE statement
   |-- Exercise 5.2: DAL methods (INSERT/UPDATE/DELETE)
   '-- Exercise 5.3+: Consumer event handlers

3. VERIFY each exercise
   |-- Trigger: curl against MongoDB backend (port 8000) to emit Kafka event
   |-- Check logs: docker compose logs mysql-service
   '-- Query MySQL: docker compose exec mysql mysql -u analytics -panalytics123 analytics

4. COMPLETE the verification checklist

5. (Optional) ATTEMPT advanced challenges

6. MOVE to next task MD
```

### The Verification Pattern (Different From MongoDB Tasks)

MongoDB tasks verify via direct HTTP response (curl -> JSON). MySQL tasks use a **three-step pattern** because the MySQL service is a background consumer:

```
Step 1: TRIGGER
   curl -X POST http://localhost:8000/users ...
   (This hits the MongoDB backend, which emits a Kafka event)

Step 2: CHECK LOGS
   docker compose logs mysql-service | grep USER_CREATED
   (Confirms the consumer received and processed the event)

Step 3: QUERY MYSQL
   docker compose exec mysql mysql -u analytics -panalytics123 analytics
   SELECT * FROM users WHERE user_id = '<id>';
   (Confirms the data landed correctly in MySQL)
```

### AI Assistant Integration

Each MD is designed so that an AI assistant can:
1. **Reference it** when helping the student
2. **Check student work** against the actual codebase implementations
3. **Give hints** without giving away the answer (3 hint levels per exercise)
4. **Validate** that the student used correct SQL patterns
5. **Explain WHY** a pattern is used (each exercise links concept to real-world need)

---

## Student Stubbing Strategy

### What Students Receive (Empty Shells)

#### `src/db/tables.py` - Empty list:
```python
"""CREATE TABLE definitions for the analytics database."""

TABLE_DEFINITIONS = [
    # Students add CREATE TABLE statements here, one per task
]
```

#### `src/dal/user_dal.py` - Class with method signatures only:
```python
"""Data Access Layer for users table."""
import logging
from src.db.connection import get_database

logger = logging.getLogger(__name__)


class UserDAL:

    def insert_user(self, user_id, email, phone, display_name, avatar, bio,
                    version, deleted_at, created_at, updated_at,
                    event_id, event_timestamp):
        """
        Insert or update a user row.

        SQL Pattern: INSERT ... ON DUPLICATE KEY UPDATE
        - Insert all 12 columns
        - On duplicate user_id: update all columns except user_id and created_at

        Args: All column values as positional parameters.
        """
        # TODO: Implement
        pass

    def soft_delete_user(self, user_id, event_id, event_timestamp):
        """
        Soft-delete a user by setting deleted_at to NOW(6).

        SQL Pattern: UPDATE ... SET ... WHERE
        - Set deleted_at = NOW(6)
        - Update event_id and event_timestamp
        - Match on user_id

        Args:
            user_id: The MongoDB ObjectId string.
            event_id: The Kafka event UUID.
            event_timestamp: When the event was emitted.
        """
        # TODO: Implement
        pass
```

#### `src/consumers/user_consumer.py` - Class with handler signatures only:
```python
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
        """Parse ISO timestamp string to datetime. Returns None if empty."""
        # TODO: Implement
        pass

    def handle_user_created(self, event: dict):
        """
        Handle USER_CREATED event.

        Event payload structure:
            event["entity_id"] -> user_id
            event["data"]["contact_info"]["primary_email"] -> email
            event["data"]["contact_info"]["phone"] -> phone
            event["data"]["profile"]["display_name"] -> display_name
            event["data"]["profile"]["avatar"] -> avatar
            event["data"]["profile"]["bio"] -> bio
            event["data"]["version"] -> version
            event["data"]["deleted_at"] -> deleted_at (parse timestamp)
            event["data"]["created_at"] -> created_at (parse timestamp)
            event["data"]["updated_at"] -> updated_at (parse timestamp)
            event["event_id"] -> event_id
            event["timestamp"] -> event_timestamp (parse timestamp)

        Action: Extract all fields above, call self._dal.insert_user(...)
        """
        # TODO: Implement
        pass

    def handle_user_updated(self, event: dict):
        """Handle USER_UPDATED event. Same logic as created (full model upsert)."""
        # TODO: Implement
        pass

    def handle_user_deleted(self, event: dict):
        """
        Handle USER_DELETED event.

        Event payload: event["data"]["user_id"] or event["entity_id"]
        Action: Call self._dal.soft_delete_user(...)
        """
        # TODO: Implement
        pass

    def get_handlers(self) -> dict:
        """Return mapping of EventType -> handler method."""
        # TODO: Implement
        pass
```

### What STAYS in the student version:
- Class definitions with `__init__`
- All method signatures with full parameter lists
- Comprehensive docstrings explaining event payload structure
- Import statements
- Helper method signatures (`_parse_ts`)

### What gets REMOVED:
- All method bodies (replaced with `pass`)
- SQL query strings
- Event field extraction logic
- `get_handlers()` return dict

---

## Exercise Design Principles

### 1. Every Exercise Targets ONE Layer
DDL exercises focus only on CREATE TABLE. DAL exercises focus only on SQL. Consumer exercises focus only on event handling. Don't mix layers.

### 2. Every Exercise Has Real Business Context
Not "create a table" but "Design the analytics table that lets the data team query user signups by date and email domain."

### 3. Three Hint Levels Per Exercise
- **Hint 1:** Direction (e.g., "Use INSERT ... ON DUPLICATE KEY UPDATE for idempotent upserts")
- **Hint 2:** Pattern (e.g., "The UPDATE clause should skip `created_at` - it's immutable after first insert")
- **Hint 3:** Near-solution (e.g., the actual SQL with minor gaps)

### 4. Verification Is Concrete
Every exercise ends with specific docker/curl/SQL commands that prove it works.

### 5. The Flattening Map Is Visual
Each task includes a clear mapping diagram showing nested MongoDB fields -> flat MySQL columns.

---

## Key Differences From MongoDB Tasks

| Aspect | MongoDB Tasks | MySQL Tasks |
|--------|--------------|-------------|
| **What students write** | Service-layer Python (Beanie ODM) | DDL + raw SQL + event handlers |
| **Trigger** | HTTP request -> immediate response | HTTP request -> Kafka event -> background consumer |
| **Verification** | curl response JSON | docker logs + SQL SELECT |
| **Data model** | Nested documents (as-is) | Flattened columns (transform required) |
| **Delete pattern** | Soft delete (set deleted_at) | Both soft (User, Post) and hard (Supplier, Product) |
| **Parent/child** | Embedded documents | Foreign key tables (Product/Variants, Order/Items) |
| **Idempotency** | Application-level checks | ON DUPLICATE KEY UPDATE (database-level) |

---

## Success Criteria

A student who completes all tasks will be able to:

1. **Design MySQL schemas** from nested document structures (flattening)
2. **Write CREATE TABLE statements** with appropriate types, indexes, and constraints
3. **Use FOREIGN KEY with ON DELETE CASCADE** for parent/child relationships
4. **Write INSERT ... ON DUPLICATE KEY UPDATE** for idempotent event processing
5. **Implement the replace pattern** (DELETE + INSERT) for child table updates
6. **Write batch INSERT loops** for multi-row writes
7. **Build Kafka event consumers** that transform and persist data
8. **Flatten nested MongoDB documents** into relational columns
9. **Use JSON columns** for semi-structured data that doesn't warrant its own table
10. **Understand selective upserts** (only updating certain columns on duplicate)
