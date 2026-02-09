# Architecture

## File System

```
kafka_mongo_sql_pipeline/
├── docker-compose.yml
│
├── shared/                              # Shared code across services
│   ├── models/                          # Pydantic + Beanie ODM models (MongoDB documents)
│   │   ├── user.py                      # User, ContactInfo, UserProfile
│   │   ├── supplier.py                  # Supplier, CompanyInfo, BusinessInfo, BankingInfo
│   │   ├── product.py                   # Product, ProductVariant, StockLocation, ProductStats
│   │   ├── order.py                     # Order, OrderItem, ProductSnapshot, ShippingAddress
│   │   └── post.py                      # Post, PostAuthor, MediaAttachment, LinkPreview, PostStats
│   ├── kafka/
│   │   ├── config.py                    # KafkaConfig (bootstrap_servers, client_id)
│   │   └── topics.py                    # Topic enum + EventType enum (24 event types)
│   └── errors.py                        # AppError hierarchy (12 error types)
│
├── apps/
│   ├── mongo_backend/                   # FastAPI application (port 8000)
│   │   ├── Dockerfile
│   │   ├── server.py                    # App factory, lifespan, exception handlers
│   │   ├── db/
│   │   │   └── connection.py            # MongoDB + Beanie initialization
│   │   ├── kafka/
│   │   │   └── producer.py              # KafkaProducer singleton (emit events)
│   │   ├── routes/                      # Controllers — request parsing, response shaping
│   │   │   ├── user.py                  # /users, /suppliers endpoints
│   │   │   ├── product.py               # /products endpoints
│   │   │   ├── order.py                 # /orders endpoints
│   │   │   └── post.py                  # /posts endpoints
│   │   ├── schemas/                     # Request/response DTOs (Pydantic)
│   │   │   ├── user.py                  # CreateUser, UpdateUser, CreateSupplier, UpdateSupplier
│   │   │   ├── product.py               # CreateProduct, UpdateProduct
│   │   │   ├── order.py                 # CreateOrder
│   │   │   └── post.py                  # CreatePost, UpdatePost
│   │   └── services/                    # Business logic layer
│   │       ├── user.py                  # UserService + SupplierService
│   │       ├── product.py               # ProductService (lifecycle state machine)
│   │       ├── order.py                 # OrderService (create, cancel)
│   │       └── post.py                  # PostService (create, publish, soft-delete)
│   │
│   └── mysql_server/                    # Kafka consumer → MySQL analytics replica
│       ├── Dockerfile
│       ├── main.py                      # Bootstrap: connect DB, init tables, start consumer
│       └── src/
│           ├── db/
│           │   ├── connection.py         # MySQL connection pool
│           │   └── tables.py             # DDL for 7 tables (users, suppliers, products, product_variants, orders, order_items, posts)
│           ├── kafka/
│           │   └── consumer.py           # KafkaConsumer orchestrator (poll → dispatch)
│           ├── consumers/                # Event handlers per domain
│           │   ├── user_consumer.py      # USER_CREATED / UPDATED / DELETED
│           │   ├── supplier_consumer.py  # SUPPLIER_CREATED / UPDATED / DELETED
│           │   ├── product_consumer.py   # PRODUCT_CREATED / UPDATED / PUBLISHED / DELETED / ...
│           │   ├── order_consumer.py     # ORDER_CREATED / CANCELLED
│           │   └── post_consumer.py      # POST_CREATED / UPDATED / PUBLISHED / DELETED
│           └── dal/                      # Data Access Layer — raw SQL
│               ├── user_dal.py           # insert_user (upsert), soft_delete_user
│               ├── supplier_dal.py       # insert_supplier (upsert), delete_supplier
│               ├── product_dal.py        # upsert_product, replace_variants, delete_product
│               ├── order_dal.py          # insert_order, insert_order_items, cancel_order
│               └── post_dal.py           # upsert_post, soft_delete_post
│
└── scripts/
    ├── seed.py                          # Seed suppliers + users via REST API
    ├── generate_posts.py                # Generate sample posts
    └── generate_products.py             # Generate sample products with variants
```

---

## Model Relationships

All models live in `shared/models/` and are Beanie `Document` subclasses backed by MongoDB.

```
┌──────────┐        product_ids[]        ┌───────────┐
│ Supplier  │◄────────────────────────────│  Product   │
│           │  1 ────────────────── many  │           │
└──────────┘                              └─────┬─────┘
                                                │
                                   ProductSnapshot (immutable copy)
                                                │
┌──────────┐   customer.user_id   ┌─────────────▼──┐
│   User    │◄────────────────────│     Order       │
│           │  1 ──────── many    │  ├─ OrderItem[] │
└─────┬─────┘                     └────────────────┘
      │
      │  author.user_id
      │  1 ──────── many
      ▼
┌──────────┐
│   Post    │
└──────────┘
```

| From | To | Relationship | Stored As |
|------|----|-------------|-----------|
| Product | Supplier | many → 1 | `product.supplier_id` (ObjectId) + `supplier.product_ids[]` back-reference |
| Order | User | many → 1 | `order.customer.user_id` (denormalized with display_name, email) |
| OrderItem | Product | many → 1 | `order_item.product_snapshot` (immutable copy at purchase time) |
| Post | User | many → 1 | `post.author.user_id` (denormalized with display_name, avatar) |

Key design choice: references are denormalized. Each Order captures a `ProductSnapshot` so price/name are frozen at purchase time. Each Post embeds a `PostAuthor` copy so timeline queries don't need joins.

---

## API — Controller & Service Layer

Every request flows through three layers:

```
HTTP Request → Route (controller) → Service (business logic) → MongoDB + Kafka
```

- **Routes** (`routes/`) parse the request, extract headers/path/query params, call the service, and return the HTTP response.
- **Services** (`services/`) own all business rules: validation, state transitions, persistence, and event emission.

### Users & Suppliers — `routes/user.py` → `services/user.py`

| Method | Endpoint | Controller Logic | Service Logic |
|--------|----------|-----------------|---------------|
| POST | `/users` | Parse `CreateUserRequest` body | Validate email uniqueness (case-insensitive), hash password, build `ContactInfo` + `UserProfile`, insert document, emit `USER_CREATED` |
| GET | `/users` | Read `skip`/`limit` query params | Filter `deleted_at=None`, return sorted list |
| GET | `/users/{id}` | Extract path param | Fetch by ObjectId, reject if soft-deleted |
| PATCH | `/users/{id}` | Parse `UpdateUserRequest` body | Merge only provided fields (display_name, phone, bio, avatar), save, emit `USER_UPDATED` |
| DELETE | `/users/{id}` | Extract path param, return 204 | Set `deleted_at = utcnow()` (soft delete), emit `USER_DELETED` |
| POST | `/suppliers` | Parse `CreateSupplierRequest` body | Validate email uniqueness, hash password, map DTO → `SupplierContactInfo` + `CompanyInfo` + `BusinessInfo` + `BankingInfo`, insert, emit `SUPPLIER_CREATED` |
| GET | `/suppliers` | Read `skip`/`limit` | Return paginated list |
| GET | `/suppliers/{id}` | Extract path param | Fetch by ObjectId |
| PATCH | `/suppliers/{id}` | Parse `UpdateSupplierRequest` body | Merge provided fields across nested objects, save, emit `SUPPLIER_UPDATED` |
| DELETE | `/suppliers/{id}` | Return 204 | Hard delete document, emit `SUPPLIER_DELETED` |

### Products — `routes/product.py` → `services/product.py`

Auth: `X-Supplier-ID` header required for write operations.

| Method | Endpoint | Controller Logic | Service Logic |
|--------|----------|-----------------|---------------|
| POST | `/products` | Read `X-Supplier-ID` header, parse body | Validate supplier exists, build variants/stock/metadata, insert with `status=DRAFT`, append to `supplier.product_ids`, emit `PRODUCT_CREATED` |
| GET | `/products` | Read `skip`, `limit`, `status`, `category`, `supplier_id` query params | Filter `status != DELETED`, apply optional filters, sort by `-created_at` |
| GET | `/products/{id}` | Extract path param | Fetch by ID, reject if `status=DELETED` |
| PATCH | `/products/{id}` | Read header + body | Partial update (name, description, category, pricing, SKU, brand, topics, locations, variants), emit `PRODUCT_UPDATED` |
| DELETE | `/products/{id}` | Read header, return 204 | Set `status=DELETED`, remove from `supplier.product_ids`, emit `PRODUCT_DELETED` |
| POST | `/products/{id}/publish` | Read header | Require `status=DRAFT`, set `ACTIVE` + `published_at`, emit `PRODUCT_PUBLISHED` |
| POST | `/products/{id}/discontinue` | Read header | Require `ACTIVE` or `OUT_OF_STOCK`, set `DISCONTINUED`, emit `PRODUCT_DISCONTINUED` |
| POST | `/products/{id}/mark-out-of-stock` | Read header | Require `ACTIVE`, set `OUT_OF_STOCK`, emit `PRODUCT_OUT_OF_STOCK` |
| POST | `/products/{id}/restore` | Read header | Set `DRAFT`, emit `PRODUCT_RESTORED` |

Product status state machine:

```
DRAFT ──publish──► ACTIVE ──discontinue──► DISCONTINUED
                     │                          │
                     │ mark-out-of-stock         │ restore
                     ▼                          ▼
               OUT_OF_STOCK ──discontinue──►  DRAFT ◄──restore──
                     │
                     └────restore────► DRAFT

Any status ──delete──► DELETED (terminal)
```

### Orders — `routes/order.py` → `services/order.py`

Auth: `X-User-ID` header.

| Method | Endpoint | Controller Logic | Service Logic |
|--------|----------|-----------------|---------------|
| POST | `/orders` | Read `X-User-ID` header, parse body | Fetch user for `OrderCustomer`, validate each product is `ACTIVE`, build `ProductSnapshot` per item (freezes price/name), generate `order_number` (`ORD-YYYYMMDD-XXXX`), insert, emit `ORDER_CREATED` |
| GET | `/orders` | Read header + `skip`/`limit`/`status` params | Filter by `customer.user_id`, optional status filter, sort `-created_at` |
| GET | `/orders/{id}` | Extract path param | Fetch by ID |
| POST | `/orders/{id}/cancel` | Read header + optional reason | Require `PENDING` or `CONFIRMED`, set `CANCELLED`, emit `ORDER_CANCELLED` |

### Posts — `routes/post.py` → `services/post.py`

Auth: `X-User-ID` header.

| Method | Endpoint | Controller Logic | Service Logic |
|--------|----------|-----------------|---------------|
| POST | `/posts` | Read `X-User-ID` header, parse body | Fetch user for `PostAuthor`, set `post_type`, attach media/link_preview, if not draft set `published_at=now`, emit `POST_CREATED` |
| GET | `/posts` | Read `skip`/`limit`/`author_id` params | Filter `deleted_at=None` and `published_at!=None`, optional author filter, sort `-published_at` |
| GET | `/posts/{id}` | Extract path param | Fetch by ID, reject if soft-deleted |
| PATCH | `/posts/{id}` | Read header + body | Partial update (text_content, media, link_preview), emit `POST_UPDATED` |
| DELETE | `/posts/{id}` | Read header, return 204 | Set `deleted_at=now` (soft delete), emit `POST_DELETED` |
| POST | `/posts/{id}/publish` | Read header | Require `published_at=None` (draft), set `published_at=now`, emit `POST_PUBLISHED` |

---

## Event-Driven Sync — MongoDB → Kafka → MySQL

Every write operation in a service emits a Kafka event. The MySQL server consumes these events to maintain a denormalized analytics replica.

```
┌─────────────────────┐     emit()     ┌─────────┐    poll()    ┌────────────────────┐
│  mongo_backend       │───────────────►│  Kafka   │◄────────────│  mysql_server       │
│  (FastAPI services)  │                │ (5 topics)│            │  (consumer + DAL)   │
│                      │                └─────────┘             │                      │
│  MongoDB ◄───────────│                                        │──────────► MySQL     │
└─────────────────────┘                                        └────────────────────┘
```

### Kafka Topics & Events

| Topic | Event Types |
|-------|-------------|
| `user` | `USER_CREATED`, `USER_UPDATED`, `USER_DELETED` |
| `supplier` | `SUPPLIER_CREATED`, `SUPPLIER_UPDATED`, `SUPPLIER_DELETED` |
| `product` | `PRODUCT_CREATED`, `PRODUCT_UPDATED`, `PRODUCT_PUBLISHED`, `PRODUCT_DISCONTINUED`, `PRODUCT_OUT_OF_STOCK`, `PRODUCT_RESTORED`, `PRODUCT_DELETED` |
| `order` | `ORDER_CREATED`, `ORDER_CANCELLED` |
| `post` | `POST_CREATED`, `POST_UPDATED`, `POST_PUBLISHED`, `POST_DELETED` |

### Event Message Format

```json
{
  "event_type": "user.created",
  "event_id": "uuid-v4",
  "timestamp": "ISO-8601",
  "entity_id": "mongo-objectid",
  "data": { }
}
```

Partition key = `entity_id`, guaranteeing ordered delivery per entity.

### Consumer → DAL Processing

Each consumer maps event types to handler methods. Handlers extract fields from `event.data` and call the corresponding DAL method.

| Consumer | Handles | DAL Methods |
|----------|---------|-------------|
| `UserConsumer` | created, updated → upsert; deleted → soft delete | `insert_user` (ON DUPLICATE KEY UPDATE), `soft_delete_user` |
| `SupplierConsumer` | created, updated → upsert; deleted → hard delete | `insert_supplier` (ON DUPLICATE KEY UPDATE), `delete_supplier` |
| `ProductConsumer` | created/updated/published/discontinued/out-of-stock/restored → upsert product + replace variants; deleted → hard delete | `upsert_product`, `replace_variants` (DELETE + INSERT), `delete_product` |
| `OrderConsumer` | created → insert order + batch insert items; cancelled → update status | `insert_order`, `insert_order_items`, `cancel_order` |
| `PostConsumer` | created/updated/published → upsert; deleted → soft delete | `upsert_post`, `soft_delete_post` |

### MySQL Schema (7 tables)

```
users                    suppliers               products
├─ user_id (PK)          ├─ supplier_id (PK)      ├─ product_id (PK)
├─ email                 ├─ email                  ├─ supplier_id (FK→suppliers)
├─ phone                 ├─ primary_phone          ├─ name, category, status
├─ display_name          ├─ legal_name             ├─ base_price_cents
├─ avatar, bio           ├─ address fields          ├─ stats counters
├─ deleted_at            ├─ social links            └─ event tracking
└─ event tracking        └─ event tracking
                                                   product_variants
orders                   order_items               ├─ id (PK, auto)
├─ order_id (PK)         ├─ id (PK, auto)          ├─ product_id (FK→products)
├─ order_number (unique) ├─ order_id (FK→orders)   ├─ variant_key (unique w/ product_id)
├─ customer_user_id      ├─ product_id              ├─ price_cents, quantity
├─ shipping fields       ├─ pricing + fulfillment   └─ dimensions
├─ status                └─ tracking info
└─ event tracking
                         posts
                         ├─ post_id (PK)
                         ├─ author_user_id
                         ├─ post_type, text_content
                         ├─ media_json, link fields
                         ├─ engagement stats
                         ├─ deleted_at, published_at
                         └─ event tracking
```

---

## Infrastructure — Docker Compose

| Service | Image | Port | Role |
|---------|-------|------|------|
| mongodb | mongo:latest | 27017 | Primary database |
| kafka | confluentinc/cp-kafka:7.6.0 | 9092 | Event streaming (KRaft mode, no Zookeeper) |
| app | FastAPI (custom Dockerfile) | 8000 | REST API |
| mysql | mysql:8.0 | 3306 | Analytics replica |
| mysql-service | Python (custom Dockerfile) | — | Kafka consumer process |

All services communicate over a shared `social_commerce_network` bridge network.
