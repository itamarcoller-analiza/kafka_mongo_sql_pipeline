# Missing Implementations - Actionable Guide

## Purpose

This document lists every file with unimplemented (`pass`) methods, explains the exact dependency chain that determines implementation order, and provides a step-by-step plan to make the project runnable.

---

## System Architecture

```
                    WHAT YOU BUILD
                    ─────────────
┌────────────────────────────────────────────────────────┐
│                    docker-compose.yml                    │
│         (5 services, environment vars, volumes)         │
└────────┬───────────────┬────────────────┬──────────────┘
         │               │                │
         v               v                v
┌──────────────┐  ┌─────────────┐  ┌────────────────┐
│   Dockerfiles │  │  Kafka Infra │  │ MySQL Consumer │
│   (2 files)   │  │  (3 files)   │  │   (11 files)   │
└──────────────┘  └─────────────┘  └────────────────┘
                        │
                        v
              ┌───────────────────┐
              │  Service Layer    │
              │   (4 files)       │
              │  34 methods       │
              └───────────────────┘
```

**Already complete (don't modify):** Models, Schemas, Routes, Utils, MongoDB init, MySQL table DDL.

---

## Implementation Inventory

### Totals

| Layer | Files | Stubbed Methods | Task Reference |
|-------|-------|-----------------|----------------|
| Dockerfiles | 2 | N/A (empty files) | TASK_DOCKER_COMPOSE |
| docker-compose.yml | 1 | N/A (env vars + volumes) | TASK_DOCKER_COMPOSE |
| Shared Kafka config | 2 | 5 | TASK_09 |
| Kafka Producer | 1 | 6 | TASK_09 |
| Kafka Consumer | 1 | 7 | TASK_09 |
| MongoDB Services | 4 | 34 | TASK_01/02/04/05/07 |
| MySQL DB Connection | 1 | 3 | TASK_08 |
| MySQL DAL | 5 | 12 | TASK_08 |
| MySQL Consumers | 5 | 28 | TASK_08 |
| **Total** | **22 files** | **95 stubs** | |

---

## Detailed File Inventory

### Layer 0: Docker Infrastructure (3 files)

**Both Dockerfiles are empty (0 bytes) - containers cannot build.**

| File | What's Missing |
|------|---------------|
| `apps/mongo_backend/Dockerfile` | Entire Dockerfile (Python image, requirements, CMD) |
| `apps/mysql_server/Dockerfile` | Entire Dockerfile (Python image, requirements, CMD) |

**`docker-compose.yml` - all 5 services stripped:**

| Service | Missing |
|---------|---------|
| `mongodb` | `MONGO_INITDB_DATABASE`, data volume |
| `kafka` | All 11 KRaft environment vars, data volume |
| `app` | `MONGODB_URL`, `DATABASE_NAME`, `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_CLIENT_ID`, bind mounts |
| `mysql` | `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, data volume |
| `mysql-service` | `KAFKA_*`, `MYSQL_*` env vars, bind mounts |
| Top-level | `volumes:` section (3 named volumes) |

**Task reference:** `TASK_DOCKER_COMPOSE.md`

---

### Layer 1: Shared Kafka Infrastructure (2 files, 5 stubs)

**`shared/kafka/config.py`** — 3 stubs

| Method | What It Does |
|--------|-------------|
| `from_env()` | Read `KAFKA_BOOTSTRAP_SERVERS` and `KAFKA_CLIENT_ID` from env |
| `to_producer_config()` | Return `{"bootstrap.servers": ..., "client.id": ...}` |
| `to_consumer_config(group_id)` | Return dict with bootstrap.servers, group.id, auto.offset.reset, etc. |

**`shared/kafka/topics.py`** — 2 stubs (but defines ~24 constants)

| Stub | What It Does |
|------|-------------|
| `Topic` class body | Define 5 topic constants: `USER`, `ORDER`, `POST`, `PRODUCT`, `SUPPLIER` |
| `Topic.all()` | Return list of all 5 topic strings |
| `EventType` class body | Define 19 event type constants in `"topic.action"` format |

**Task reference:** `TASK_09_KAFKA.md` (Exercises 2 & 3)

---

### Layer 2: Kafka Producer (1 file, 6 stubs)

**`apps/mongo_backend/kafka/producer.py`** — 6 stubs

| Method | What It Does |
|--------|-------------|
| `__init__(config)` | Create `KafkaConfig.from_env()` + `confluent_kafka.Producer` |
| `_delivery_callback(err, msg)` | Log delivery success/failure |
| `send(topic, value, key)` | JSON-serialize value, encode key, call `producer.produce()` |
| `flush(timeout)` | Flush pending messages |
| `emit(event_type, entity_id, data)` | Build event envelope, extract topic, call `send()` |
| `get_kafka_producer()` | Module-level singleton factory |

**Why this is critical:** Every service class calls `get_kafka_producer()` in its `__init__`. If this returns `None`, the app starts but every endpoint that calls `self._kafka.emit()` will crash with `AttributeError`.

**Task reference:** `TASK_09_KAFKA.md` (Exercise 4)

---

### Layer 3: MongoDB Service Layer (4 files, 34 stubs)

**`apps/mongo_backend/services/user.py`** — 10 stubs

| Method | Endpoint | Domain |
|--------|----------|--------|
| `create_user()` | `POST /users` | User |
| `get_user()` | `GET /users/{id}` | User |
| `list_users()` | `GET /users` | User |
| `update_user()` | `PATCH /users/{id}` | User |
| `delete_user()` | `DELETE /users/{id}` | User |
| `create_supplier()` | `POST /suppliers` | Supplier |
| `get_supplier()` | `GET /suppliers/{id}` | Supplier |
| `list_suppliers()` | `GET /suppliers` | Supplier |
| `update_supplier()` | `PATCH /suppliers/{id}` | Supplier |
| `delete_supplier()` | `DELETE /suppliers/{id}` | Supplier |

**Task reference:** `TASK_01_USER.md`, `TASK_02_SUPPLIER.md`

**`apps/mongo_backend/services/product.py`** — 12 stubs

| Method | Endpoint |
|--------|----------|
| `_build_topic_descriptions()` | Helper (used by create/update) |
| `_build_stock_locations()` | Helper (used by create/update) |
| `_build_variants()` | Helper (used by create/update) |
| `create_product()` | `POST /products` |
| `get_product()` | `GET /products/{id}` |
| `list_products()` | `GET /products` |
| `update_product()` | `PATCH /products/{id}` |
| `delete_product()` | `DELETE /products/{id}` |
| `publish_product()` | `POST /products/{id}/publish` |
| `discontinue_product()` | `POST /products/{id}/discontinue` |
| `mark_out_of_stock()` | `POST /products/{id}/mark-out-of-stock` |
| `restore_product()` | `POST /products/{id}/restore` |

**Task reference:** `TASK_04_PRODUCT.md`

**`apps/mongo_backend/services/post.py`** — 8 stubs

| Method | Endpoint |
|--------|----------|
| `_build_media()` | Helper |
| `_build_link_preview()` | Helper |
| `create_post()` | `POST /posts` |
| `get_post()` | `GET /posts/{id}` |
| `list_posts()` | `GET /posts` |
| `update_post()` | `PATCH /posts/{id}` |
| `delete_post()` | `DELETE /posts/{id}` |
| `publish_post()` | `POST /posts/{id}/publish` |

**Task reference:** `TASK_05_POST.md`

**`apps/mongo_backend/services/order.py`** — 4 stubs

| Method | Endpoint |
|--------|----------|
| `create_order()` | `POST /orders` |
| `get_order()` | `GET /orders/{id}` |
| `list_orders()` | `GET /orders` |
| `cancel_order()` | `POST /orders/{id}/cancel` |

**Task reference:** `TASK_07_ORDER.md`

---

### Layer 4: MySQL Analytics Pipeline (12 files, 50 stubs)

**`apps/mysql_server/src/db/connection.py`** — 3 stubs

| Method | What It Does |
|--------|-------------|
| `connect()` | Create MySQL connection pool from env vars |
| `init_tables()` | Execute all CREATE TABLE statements from `tables.py` |
| `get_connection()` | Return a connection from the pool |

**`apps/mysql_server/src/kafka/consumer.py`** — 7 stubs

| Method | What It Does |
|--------|-------------|
| `__init__(group_id)` | Create KafkaConfig, Consumer, handlers dict |
| `register_handler()` | Store handler by event_type |
| `subscribe(topics)` | Subscribe consumer to topics |
| `_process_message(msg)` | JSON decode, route to handler |
| `start()` | Poll loop with error handling |
| `stop()` | Set running=False, close consumer |
| `_setup_signal_handlers()` | SIGINT/SIGTERM graceful shutdown |

**5 Consumer files** — 28 stubs total

| File | Stubs | Handles |
|------|-------|---------|
| `consumers/user_consumer.py` | 5 + `get_handlers()` | USER_CREATED/UPDATED/DELETED |
| `consumers/supplier_consumer.py` | 5 + `get_handlers()` | SUPPLIER_CREATED/UPDATED/DELETED |
| `consumers/product_consumer.py` | 9 + `get_handlers()` | 7 product lifecycle events |
| `consumers/order_consumer.py` | 3 + `get_handlers()` | ORDER_CREATED/CANCELLED |
| `consumers/post_consumer.py` | 6 + `get_handlers()` | POST_CREATED/UPDATED/PUBLISHED/DELETED |

**5 DAL files** — 12 stubs total

| File | Stubs | SQL Operations |
|------|-------|---------------|
| `dal/user_dal.py` | 2 | `insert_user` (upsert), `soft_delete_user` |
| `dal/supplier_dal.py` | 2 | `insert_supplier` (upsert), `delete_supplier` |
| `dal/product_dal.py` | 3 | `upsert_product`, `replace_variants`, `delete_product` |
| `dal/order_dal.py` | 3 | `insert_order`, `insert_order_items`, `cancel_order` |
| `dal/post_dal.py` | 2 | `upsert_post`, `soft_delete_post` |

**Task reference:** `TASK_09_KAFKA.md` (Exercises 5), `TASK_08_ANALYTICS.md`

---

## Dependency Chain (What Blocks What)

Understanding this chain is essential. You cannot skip layers.

```
Dockerfiles + docker-compose.yml          LAYER 0: Nothing works without this
        │
        v
shared/kafka/config.py                   LAYER 1: Required by both producer
shared/kafka/topics.py                            and consumer
        │
        ├─────────────────────────┐
        v                         v
Kafka Producer                    Kafka Consumer
(producer.py)                     (consumer.py)
        │                         │
        v                         v
Service Layer                     MySQL Connection
(user.py, product.py,            (connection.py)
 order.py, post.py)              │
        │                         v
        │                    MySQL DAL Layer
        │                    (5 dal/*.py files)
        │                         │
        │                         v
        │                    Domain Consumers
        │                    (5 consumers/*.py)
        v                         │
   MongoDB Backend          MySQL Analytics
   (Port 8000)              Service
```

### Critical insight: The import chain

When the FastAPI app starts:

1. `server.py` imports route files
2. Route files execute `UserService()`, `ProductService()`, etc. **at module level**
3. Each service `__init__` calls `get_kafka_producer()`
4. `get_kafka_producer()` calls `KafkaProducer()`
5. `KafkaProducer.__init__` calls `KafkaConfig.from_env()` then `confluent_kafka.Producer(config)`

**If `KafkaConfig.from_env()` returns `None` (because it's `pass`):** `Producer(None)` crashes.

**If Kafka broker is unreachable:** `Producer(valid_config)` still creates the object - it only fails when you actually `produce()` a message. So the app can start without a Kafka broker, as long as the config is valid.

---

## Implementation Order

### Phase 1: Docker Infrastructure

**Goal:** Containers can build and start.

| Step | File | What to Do | Reference |
|------|------|-----------|-----------|
| 1a | `apps/mongo_backend/Dockerfile` | Write Dockerfile (Python 3.11, install requirements, CMD uvicorn) | TASK_DOCKER_COMPOSE |
| 1b | `apps/mysql_server/Dockerfile` | Write Dockerfile (Python 3.11, install requirements, CMD python main.py) | TASK_DOCKER_COMPOSE |
| 1c | `docker-compose.yml` | Fill in all environment vars and volumes for all 5 services | TASK_DOCKER_COMPOSE |

**Verify:** `docker compose build` succeeds, `docker compose up -d` starts all containers.

---

### Phase 2: Kafka Infrastructure

**Goal:** The FastAPI app can start without crashing. Services can call `emit()`.

| Step | File | Stubs | Reference |
|------|------|-------|-----------|
| 2a | `shared/kafka/config.py` | 3 methods | TASK_09 Exercise 2 |
| 2b | `shared/kafka/topics.py` | Topic + EventType constants | TASK_09 Exercise 3 |
| 2c | `apps/mongo_backend/kafka/producer.py` | 6 methods | TASK_09 Exercise 4 |

**Verify:** `docker compose restart app`, `docker compose logs app` shows "Application started successfully". Open `http://localhost:8000/docs` - Swagger UI loads. Health endpoint returns `{"status": "ok"}`.

**Note:** At this point all API endpoints exist but return nothing (service methods are `pass`). Calling any endpoint returns `null` or errors, which is expected.

---

### Phase 3: MongoDB Service Layer

**Goal:** API endpoints return real data from MongoDB.

Complete these in order - each task builds on the previous:

| Step | File | Stubs | Reference |
|------|------|-------|-----------|
| 3a | `services/user.py` — User methods | 5 methods | TASK_01 |
| 3b | `services/user.py` — Supplier methods | 5 methods | TASK_02 |
| 3c | `services/product.py` | 12 methods | TASK_04 |
| 3d | `services/post.py` | 8 methods | TASK_05 |
| 3e | `services/order.py` | 4 methods | TASK_07 |

**Verify each step:** Use Swagger UI (`http://localhost:8000/docs`) to create, read, update, delete entities. Check `docker compose logs -f app` for errors.

---

### Phase 4: MySQL Analytics Pipeline

**Goal:** Kafka events flow from MongoDB backend to MySQL analytics tables.

| Step | File | Stubs | Reference |
|------|------|-------|-----------|
| 4a | `apps/mysql_server/src/db/connection.py` | 3 methods | TASK_08 |
| 4b | `apps/mysql_server/src/kafka/consumer.py` | 7 methods | TASK_09 Exercise 5 |
| 4c | `consumers/user_consumer.py` + `dal/user_dal.py` | 5 + 2 | TASK_08 |
| 4d | `consumers/supplier_consumer.py` + `dal/supplier_dal.py` | 5 + 2 | TASK_08 |
| 4e | `consumers/product_consumer.py` + `dal/product_dal.py` | 9 + 3 | TASK_08 |
| 4f | `consumers/order_consumer.py` + `dal/order_dal.py` | 3 + 3 | TASK_08 |
| 4g | `consumers/post_consumer.py` + `dal/post_dal.py` | 6 + 2 | TASK_08 |

**Verify:** `docker compose logs -f mysql-service` shows "Consumer started, waiting for messages..." and processes events when you create/update entities via the API.

---

## What's Already Complete (Don't Modify)

These files are fully implemented and should not be changed:

| Category | Files |
|----------|-------|
| **Data Models** | `shared/models/user.py`, `supplier.py`, `product.py`, `order.py`, `post.py` |
| **Error Hierarchy** | `shared/errors.py` (12 error types) |
| **Request/Response Schemas** | `apps/mongo_backend/schemas/user.py`, `product.py`, `order.py`, `post.py` |
| **Route Handlers** | `apps/mongo_backend/routes/user.py`, `product.py`, `order.py`, `post.py` |
| **Server Setup** | `apps/mongo_backend/server.py` (FastAPI app, exception handlers, route registration) |
| **MongoDB Init** | `apps/mongo_backend/db/mongo_db.py` (Motor client + Beanie init) |
| **Utility Functions** | `apps/mongo_backend/utils/` (datetime, password, serialization, response formatters) |
| **MySQL Table DDL** | `apps/mysql_server/src/db/tables.py` (7 table definitions) |
| **MySQL main.py** | `apps/mysql_server/main.py` (startup sequence) |

---

## Seed Scripts (Run After Phase 3)

After implementing the service layer, populate the database with test data:

```bash
# Step 1: Create 1 user + 30 suppliers via REST API
python scripts/seed.py

# Step 2: Create 50 products (requires suppliers)
python scripts/generate_products.py

# Step 3: Create 100 posts (writes directly to MongoDB, requires users)
python scripts/generate_posts.py
```

Scripts require `pip install requests motor beanie pydantic pydantic[email]` locally.

---

## Quick Reference: Where Each Task File Sends You

| Task File | What You Implement | Files You Edit |
|-----------|-------------------|----------------|
| `TASK_DOCKER_COMPOSE.md` | Docker infrastructure | `docker-compose.yml`, 2 Dockerfiles |
| `TASK_00_SETUP.md` | Nothing (read-only orientation) | - |
| `TASK_01_USER.md` | User CRUD | `services/user.py` (5 methods) |
| `TASK_02_SUPPLIER.md` | Supplier CRUD | `services/user.py` (5 methods) |
| `TASK_04_PRODUCT.md` | Product CRUD + lifecycle | `services/product.py` (12 methods) |
| `TASK_05_POST.md` | Post CRUD + publish | `services/post.py` (8 methods) |
| `TASK_07_ORDER.md` | Order CRUD + cancel | `services/order.py` (4 methods) |
| `TASK_08_ANALYTICS.md` | MySQL connection, DAL, consumers | `connection.py`, 5 DAL files, 5 consumer files |
| `TASK_09_KAFKA.md` | Kafka config, topics, producer, consumer | `config.py`, `topics.py`, `producer.py`, `consumer.py` |
