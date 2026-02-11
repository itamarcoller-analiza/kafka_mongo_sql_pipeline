# Quickstart: How to Implement

## What You're Building

5 CRUD services that talk to MongoDB, emit Kafka events, and sync to MySQL.

```
Route (done) → Service (YOU) → MongoDB
                    ↓
                Kafka event
                    ↓
           MySQL Consumer (YOU)
```

Every service follows the same pattern: **fetch → validate → act → save → emit event → return**.

The routes are already wired. You just fill in the service methods (all `pass` stubs).

---

## How to Read the Code

Follow this exact path for each domain:

```
1.  apps/mongo_backend/main.py          → sees how uvicorn starts the app
2.  apps/mongo_backend/server.py        → sees route registration order + DB init
3.  apps/mongo_backend/routes/user.py   → sees how routes call YOUR service
4.  apps/mongo_backend/services/user.py → YOUR TODO stubs (start implementing here)
5.  shared/models/user.py              → the MongoDB document structure
6.  apps/mongo_backend/schemas/user.py  → what the request body looks like
```

For the Kafka + MySQL side:

```
7.  shared/kafka/topics.py             → topic names + event types (TODO)
8.  shared/kafka/config.py             → Kafka connection config (TODO)
9.  apps/mongo_backend/kafka/producer.py → event producer (TODO)
10. apps/mysql_server/main.py          → sees how consumer registers handlers
11. apps/mysql_server/src/kafka/consumer.py → Kafka consumer loop (TODO)
12. apps/mysql_server/src/consumers/user_consumer.py → event handler (TODO)
13. apps/mysql_server/src/dal/user_dal.py → MySQL INSERT/UPDATE (TODO)
```

Then repeat steps 3-6 and 12-13 for each domain: supplier → product → post → order.

---

## What to Read in the Task MDs

**Read these sections:**
- **Section 3: Model Deep Dive** — the document structure you're building
- **Section 4: Service Contract** — method signatures and what each returns
- **Section 5: Exercises** — the step-by-step algorithms and code snippets

**Skip these sections:**
- Section 1 (Mission Briefing) — motivation text, not needed
- Section 2 (Before You Start) — prerequisite reminders
- Section 7 (Advanced Challenges) — optional, do after
- Section 8 (What's Next) — summary text

The exercises give you the algorithm as numbered steps. That's your implementation blueprint.

---

## The Services at a Glance

Every service does roughly the same thing:

| Method | Pattern |
|--------|---------|
| `create_*` | Check duplicates/validate → build document → `insert()` → emit event |
| `get_*` | `Model.get(PydanticObjectId(id))` → check not deleted → return |
| `list_*` | `Model.find(filters).sort().skip().limit().to_list()` |
| `update_*` | `get_*()` → update non-None fields → `save()` → emit event |
| `delete_*` | `get_*()` → soft delete or status change → `save()` → emit event |

Differences per domain:

| Service | Special |
|---------|---------|
| **User** | Soft delete (`deleted_at`), email uniqueness check, password hashing |
| **Supplier** | Hard delete (`await supplier.delete()`), deeply nested embedded docs |
| **Product** | Dict-based variants, 5-state lifecycle, supplier back-reference (`product_ids`) |
| **Post** | Author denormalization via `build_post_author()`, draft/publish with `published_at` |
| **Order** | Cross-collection validation (user + products), product snapshot, order number generation via utils |

---

## Two Implementation Strategies

### Strategy A: All MongoDB First, Then Kafka, Then MySQL

Complete all FastAPI services → then wire Kafka → then build MySQL pipeline.

```
Phase 1 — MongoDB Services (apps/mongo_backend/services/)
  1. user.py        → TASK_01  (5 user methods)
  2. user.py        → TASK_02  (5 supplier methods, same file)
  3. product.py     → TASK_04  (3 helpers + 4 CRUD + 4 lifecycle)
  4. post.py        → TASK_05  (2 helpers + 6 methods)
  5. order.py       → TASK_07  (4 methods)
  6. analytics.py   → TASK_08  (8 aggregation pipelines, create new file)

Phase 2 — Kafka Infrastructure (TASK_09)
  1. docker-compose.yml        → Kafka + all service env vars
  2. shared/kafka/topics.py    → 5 topics + 18 event types
  3. shared/kafka/config.py    → from_env, to_producer_config, to_consumer_config
  4. apps/mongo_backend/kafka/producer.py → send, emit, singleton

Phase 3 — MySQL Pipeline (TASK_09)
  1. apps/mysql_server/src/db/connection.py → connection pool
  2. apps/mysql_server/src/kafka/consumer.py → poll loop + handler routing
  3. apps/mysql_server/src/consumers/*.py   → 5 domain consumers
  4. apps/mysql_server/src/dal/*.py         → 5 DALs with SQL
```

**Pros:** You can test all API endpoints immediately via Swagger without Kafka running. Kafka events will silently fail (producer is a stub) but CRUD works.

**Cons:** You won't see events flowing until Phase 2+3 are done.

---

### Strategy B: One Domain End-to-End, Then Next

For each domain, implement the full pipeline: service → Kafka → consumer → MySQL.

```
Round 0 — Infrastructure (do once)
  1. docker-compose.yml         → all env vars + volumes
  2. shared/kafka/topics.py     → all topics + event types
  3. shared/kafka/config.py     → all 3 methods
  4. apps/mongo_backend/kafka/producer.py → full producer
  5. apps/mysql_server/src/db/connection.py → pool + init_tables
  6. apps/mysql_server/src/kafka/consumer.py → full consumer

Round 1 — User
  1. apps/mongo_backend/services/user.py     → 5 user methods
  2. apps/mysql_server/src/consumers/user_consumer.py
  3. apps/mysql_server/src/dal/user_dal.py

Round 2 — Supplier
  1. apps/mongo_backend/services/user.py     → 5 supplier methods
  2. apps/mysql_server/src/consumers/supplier_consumer.py
  3. apps/mysql_server/src/dal/supplier_dal.py

Round 3 — Product
  1. apps/mongo_backend/services/product.py
  2. apps/mysql_server/src/consumers/product_consumer.py
  3. apps/mysql_server/src/dal/product_dal.py

Round 4 — Post
  1. apps/mongo_backend/services/post.py
  2. apps/mysql_server/src/consumers/post_consumer.py
  3. apps/mysql_server/src/dal/post_dal.py

Round 5 — Order
  1. apps/mongo_backend/services/order.py
  2. apps/mysql_server/src/consumers/order_consumer.py
  3. apps/mysql_server/src/dal/order_dal.py

Round 6 — Analytics
  1. apps/mongo_backend/services/analytics.py (no Kafka/MySQL)
```

**Pros:** You see the full event flow (API → Kafka → MySQL) for each domain before moving on. Easier to debug.

**Cons:** Requires infrastructure (Round 0) to be done first before any service works.

---

## File Count Summary

| Layer | Files | Total Methods |
|-------|-------|---------------|
| MongoDB Services | 4 files (+1 new) | ~42 methods |
| Kafka Infrastructure | 4 files | ~12 methods |
| MySQL Consumers | 5 files | ~15 handlers |
| MySQL DALs | 5 files | ~12 methods |
| Docker + DB Setup | 3 files | — |
| **Total** | **22 files** | **~81 methods** |
