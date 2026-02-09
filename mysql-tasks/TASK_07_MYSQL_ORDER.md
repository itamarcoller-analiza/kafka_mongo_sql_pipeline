# TASK 07: Order - MySQL Analytics Consumer

## 1. MISSION BRIEFING

You are building the **order analytics pipeline** - the capstone of the MySQL tasks. Orders are the most complex domain because they combine everything you've learned: parent/child tables, foreign keys, batch inserts, selective upserts, and nested snapshot flattening.

In MongoDB, an order document contains a denormalized customer snapshot, a shipping address, and an array of order items — each with an embedded product snapshot frozen at purchase time. You must split this into two relational tables and handle the most nuanced upsert logic yet.

This task introduces:
- **UNIQUE KEY on a business field** — `order_number` is a natural key separate from the PK
- **Selective ON DUPLICATE KEY UPDATE** — only update `status` and timestamps, not immutable customer/shipping data
- **Batch INSERT in a loop** — inserting multiple order items from a list
- **Product snapshot flattening** — nested snapshot objects inside each item
- **Cancel by business key** — UPDATE WHERE `order_number` (not the PK)
- Only **2 event types**, but the most complex handler logic of any domain

### What You Will Build

| Layer | File | What You Implement |
|-------|------|--------------------|
| DDL | `src/db/tables.py` | `CREATE TABLE orders` (19 cols, UNIQUE, 3 indexes) + `CREATE TABLE order_items` (20 cols, FK CASCADE, composite UNIQUE) |
| DAL | `src/dal/order_dal.py` | `insert_order()` (selective upsert) + `insert_order_items()` (batch) + `cancel_order()` |
| Consumer | `src/consumers/order_consumer.py` | 2 event handlers with multi-table writes and snapshot flattening |

### What You Will Learn

| SQL Concept | Where You'll Use It |
|-------------|-------------------|
| `UNIQUE KEY` on business field | `order_number` — human-readable unique ID separate from PK |
| Selective `ON DUPLICATE KEY UPDATE` | Only update status/timestamps on orders, only update fulfillment fields on items |
| Batch INSERT in a loop | Inserting N order items from a list |
| Composite `UNIQUE KEY` on child | `(order_id, item_id)` prevents duplicate items |
| `FOREIGN KEY ON DELETE CASCADE` | Deleting an order auto-deletes its items |
| `JSON` column | `variant_attributes_json` for item variant attributes |
| UPDATE by non-PK field | `cancel_order` uses `WHERE order_number = %s` |
| `json.dumps()` in DAL | Serializing variant attributes dict in the DAL layer |

---

## 2. BEFORE YOU START

### Prerequisites
- TASK_01, TASK_02, TASK_04, and TASK_05 completed
- All 5 Docker containers running

### Files You MUST Read Before Coding

#### Step 1: The MongoDB Order Model
```
shared/models/order.py
```
Pay attention to:
- `OrderCustomer` embedded document: `user_id`, `display_name`, `email`, `phone` — denormalized snapshot of the buyer
- `ShippingAddress` embedded document: `recipient_name`, `phone`, `street_address_1/2`, `city`, `state`, `zip_code`, `country`
- `OrderItem` with `ProductSnapshot` embedded document: `product_id`, `supplier_id`, `product_name`, `variant_name`, `variant_attributes`, `image_url`, `supplier_name` — frozen product data at purchase time
- `OrderItem` fulfillment fields: `quantity`, `unit_price_cents`, `final_price_cents`, `total_cents`, `fulfillment_status`, `shipped_quantity`, `tracking_number`, `carrier`, `shipped_at`, `delivered_at`
- `order_number` — human-readable ID like `"ORD-20250115-ABC1"`

#### Step 2: The Student Files
```
apps/mysql_server/src/dal/order_dal.py
apps/mysql_server/src/consumers/order_consumer.py
```

#### Step 3: The Kafka Event Types
```
shared/kafka/topics.py
```
The Order domain has only **2** event types:
- `EventType.ORDER_CREATED` = `"order.created"`
- `EventType.ORDER_CANCELLED` = `"order.cancelled"`

---

## 3. SCHEMA DEEP DIVE

### Table 1: `orders` (Parent)

```
orders
├── order_id                VARCHAR(24)   PRIMARY KEY
├── order_number            VARCHAR(50)   NOT NULL       ← data.order_number
├── customer_user_id        VARCHAR(24)   NOT NULL       ← data.customer.user_id
├── customer_display_name   VARCHAR(200)                 ← data.customer.display_name
├── customer_email          VARCHAR(255)                 ← data.customer.email
├── customer_phone          VARCHAR(50)                  ← data.customer.phone
├── shipping_recipient_name VARCHAR(200)                 ← data.shipping_address.recipient_name
├── shipping_phone          VARCHAR(50)                  ← data.shipping_address.phone
├── shipping_street_1       VARCHAR(200)                 ← data.shipping_address.street_address_1
├── shipping_street_2       VARCHAR(200)                 ← data.shipping_address.street_address_2
├── shipping_city           VARCHAR(100)                 ← data.shipping_address.city
├── shipping_state          VARCHAR(100)                 ← data.shipping_address.state
├── shipping_zip_code       VARCHAR(20)                  ← data.shipping_address.zip_code
├── shipping_country        VARCHAR(2)                   ← data.shipping_address.country
├── status                  VARCHAR(20)   NOT NULL       ← data.status
├── created_at              DATETIME(6)   NOT NULL
├── updated_at              DATETIME(6)   NOT NULL
├── event_id                VARCHAR(36)
├── event_timestamp         DATETIME(6)
│
├── UNIQUE KEY uq_order_number (order_number)
├── INDEX idx_orders_customer (customer_user_id)
├── INDEX idx_orders_status (status)
└── INDEX idx_orders_created (created_at)
```

### Table 2: `order_items` (Child)

```
order_items
├── id                      INT           AUTO_INCREMENT PRIMARY KEY
├── order_id                VARCHAR(24)   NOT NULL       ← parent FK
├── item_id                 VARCHAR(50)   NOT NULL       ← item.item_id
├── product_id              VARCHAR(24)   NOT NULL       ← item.product_snapshot.product_id
├── supplier_id             VARCHAR(24)   NOT NULL       ← item.product_snapshot.supplier_id
├── product_name            VARCHAR(200)                 ← item.product_snapshot.product_name
├── variant_name            VARCHAR(200)                 ← item.product_snapshot.variant_name
├── variant_attributes_json JSON                         ← item.product_snapshot.variant_attributes
├── image_url               TEXT                         ← item.product_snapshot.image_url
├── supplier_name           VARCHAR(200)                 ← item.product_snapshot.supplier_name
├── quantity                INT           NOT NULL       ← item.quantity
├── unit_price_cents        INT           NOT NULL       ← item.unit_price_cents
├── final_price_cents       INT           NOT NULL       ← item.final_price_cents
├── total_cents             INT           NOT NULL       ← item.total_cents
├── fulfillment_status      VARCHAR(20)                  ← item.fulfillment_status
├── shipped_quantity        INT           DEFAULT 0      ← item.shipped_quantity
├── tracking_number         VARCHAR(100)                 ← item.tracking_number
├── carrier                 VARCHAR(100)                 ← item.carrier
├── shipped_at              DATETIME(6)                  ← item.shipped_at
├── delivered_at            DATETIME(6)                  ← item.delivered_at
│
├── UNIQUE KEY uq_order_item (order_id, item_id)
├── INDEX idx_items_order (order_id)
├── INDEX idx_items_product (product_id)
└── CONSTRAINT fk_items_order FOREIGN KEY (order_id)
        REFERENCES orders(order_id) ON DELETE CASCADE
```

### Key Design Differences From Product

| Aspect | Product + Variants | Order + Items |
|--------|-------------------|---------------|
| Child update strategy | **Replace** (DELETE + INSERT all) | **Selective upsert** (ON DUPLICATE KEY UPDATE fulfillment fields only) |
| Why | Variants change arbitrarily on every update | Order items are immutable after creation; only fulfillment status changes |
| Parent update strategy | Full upsert (all columns) | Selective upsert (only `status`, `updated_at`, event fields) |
| Why | Product data changes freely | Customer/shipping data is frozen at order time |

### UNIQUE KEY vs PRIMARY KEY

The `orders` table has **two** uniqueness constraints:
- `PRIMARY KEY (order_id)` — the MongoDB ObjectId, used for FK references from `order_items`
- `UNIQUE KEY (order_number)` — the human-readable business ID (e.g., `"ORD-20250115-ABC1"`), used for cancel operations

Why both? The `order_id` is the technical key (24-char hex, fast for joins and FKs). The `order_number` is the business key (human-readable, used in customer-facing UIs and the cancel API). The cancel event sends `order_number`, not `order_id`.

---

## 4. THE FLATTENING MAP

### Orders Table

```
MongoDB Document (nested)                    MySQL Column (flat)
===========================                  ===================

event.entity_id ───────────────────────────> order_id
data.order_number ─────────────────────────> order_number

data.customer ──────────┐
  .user_id ─────────────┼─────────────────> customer_user_id
  .display_name ────────┼─────────────────> customer_display_name
  .email ───────────────┼─────────────────> customer_email
  .phone ───────────────┘─────────────────> customer_phone

data.shipping_address ──┐
  .recipient_name ──────┼─────────────────> shipping_recipient_name
  .phone ───────────────┼─────────────────> shipping_phone
  .street_address_1 ────┼─────────────────> shipping_street_1
  .street_address_2 ────┼─────────────────> shipping_street_2
  .city ────────────────┼─────────────────> shipping_city
  .state ───────────────┼─────────────────> shipping_state
  .zip_code ────────────┼─────────────────> shipping_zip_code
  .country ─────────────┘─────────────────> shipping_country

data.status ───────────────────────────────> status
data.created_at ───────────────────────────> created_at
data.updated_at ───────────────────────────> updated_at
event.event_id ────────────────────────────> event_id
event.timestamp ───────────────────────────> event_timestamp
```

### Order Items Table

For each item in `data.items[]`:

```
MongoDB OrderItem (nested)                   MySQL Column (flat)
==============================               ===================

item.item_id ──────────────────────────────> item_id

item.product_snapshot ──┐
  .product_id ──────────┼─────────────────> product_id
  .supplier_id ─────────┼─────────────────> supplier_id
  .product_name ────────┼─────────────────> product_name
  .variant_name ────────┼─────────────────> variant_name
  .variant_attributes ──┼─────────────────> variant_attributes_json  ← json.dumps()
  .image_url ───────────┼─────────────────> image_url
  .supplier_name ───────┘─────────────────> supplier_name

item.quantity ─────────────────────────────> quantity
item.unit_price_cents ─────────────────────> unit_price_cents
item.final_price_cents ────────────────────> final_price_cents
item.total_cents ──────────────────────────> total_cents
item.fulfillment_status ───────────────────> fulfillment_status
item.shipped_quantity ─────────────────────> shipped_quantity
item.tracking_number ──────────────────────> tracking_number
item.carrier ──────────────────────────────> carrier
item.shipped_at ───────────────────────────> shipped_at
item.delivered_at ─────────────────────────> delivered_at
```

### The Event Payloads

**ORDER_CREATED** (full document with items):
```json
{
  "event_type": "order.created",
  "event_id": "uuid-string",
  "entity_id": "fff000eee111ddd222ccc333",
  "timestamp": "2025-01-15T14:00:00Z",
  "data": {
    "order_number": "ORD-20250115-ABC1",
    "customer": {
      "user_id": "507f1f77bcf86cd799439011",
      "display_name": "Jane Smith",
      "email": "jane@example.com",
      "phone": "+1234567890"
    },
    "shipping_address": {
      "recipient_name": "Jane Smith",
      "phone": "+1234567890",
      "street_address_1": "456 Oak Ave",
      "street_address_2": "Apt 7B",
      "city": "San Francisco",
      "state": "CA",
      "zip_code": "94102",
      "country": "US"
    },
    "items": [
      {
        "item_id": "item-001",
        "product_snapshot": {
          "product_id": "abc123def456abc123def456",
          "supplier_id": "60a7b2c3d4e5f6a7b8c9d0e1",
          "product_name": "Handmade Ceramic Mug",
          "variant_name": "Small White",
          "variant_attributes": {"size": "small", "color": "white"},
          "image_url": "https://cdn.example.com/mug.jpg",
          "supplier_name": "Acme Ceramics"
        },
        "quantity": 2,
        "unit_price_cents": 2500,
        "final_price_cents": 2500,
        "total_cents": 5000,
        "fulfillment_status": "pending",
        "shipped_quantity": 0,
        "tracking_number": null,
        "carrier": null,
        "shipped_at": null,
        "delivered_at": null
      }
    ],
    "status": "pending",
    "created_at": "2025-01-15T14:00:00Z",
    "updated_at": "2025-01-15T14:00:00Z"
  }
}
```

**ORDER_CANCELLED** (minimal payload):
```json
{
  "event_type": "order.cancelled",
  "event_id": "uuid-string",
  "entity_id": "fff000eee111ddd222ccc333",
  "timestamp": "2025-01-15T15:00:00Z",
  "data": {
    "order_number": "ORD-20250115-ABC1"
  }
}
```

Note: The cancel event sends `order_number` (the business key), not `order_id` (the PK).

---

## 5. IMPLEMENTATION EXERCISES

---

### Exercise 5.1: Define the `orders` Table (DDL)

**Concept:** UNIQUE KEY on business field, customer/shipping snapshot columns
**Difficulty:** Medium

#### Implement: Add the `orders` table DDL to `TABLE_DEFINITIONS` in `src/db/tables.py`

```sql
CREATE TABLE IF NOT EXISTS orders (
    order_id                VARCHAR(24) PRIMARY KEY,
    order_number            VARCHAR(50) NOT NULL,
    customer_user_id        VARCHAR(24) NOT NULL,
    customer_display_name   VARCHAR(200),
    customer_email          VARCHAR(255),
    customer_phone          VARCHAR(50),
    shipping_recipient_name VARCHAR(200),
    shipping_phone          VARCHAR(50),
    shipping_street_1       VARCHAR(200),
    shipping_street_2       VARCHAR(200),
    shipping_city           VARCHAR(100),
    shipping_state          VARCHAR(100),
    shipping_zip_code       VARCHAR(20),
    shipping_country        VARCHAR(2),
    status                  VARCHAR(20) NOT NULL,
    created_at              DATETIME(6) NOT NULL,
    updated_at              DATETIME(6) NOT NULL,
    event_id                VARCHAR(36),
    event_timestamp         DATETIME(6),
    UNIQUE KEY uq_order_number (order_number),
    INDEX idx_orders_customer (customer_user_id),
    INDEX idx_orders_status (status),
    INDEX idx_orders_created (created_at)
)
```

**Key design decisions:**
- `UNIQUE KEY uq_order_number (order_number)` — separate from the PRIMARY KEY. This ensures no two orders share the same human-readable number. The cancel operation uses this field to find the order
- No `total_cents` column on the `orders` table — the order total is derived by summing `total_cents` across `order_items`. This avoids data duplication and keeps the totals consistent
- Customer and shipping fields are **snapshots** — they capture the data at order time. If the user later changes their address, the order retains the original shipping address

---

### Exercise 5.2: Define the `order_items` Table (DDL)

**Concept:** Child table with composite UNIQUE, FK CASCADE, product snapshot columns, JSON column
**Difficulty:** Hard

#### Implement: Add the `order_items` table DDL to `TABLE_DEFINITIONS`

This **must** come after the `orders` table definition (FK references `orders`):

```sql
CREATE TABLE IF NOT EXISTS order_items (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    order_id                VARCHAR(24) NOT NULL,
    item_id                 VARCHAR(50) NOT NULL,
    product_id              VARCHAR(24) NOT NULL,
    supplier_id             VARCHAR(24) NOT NULL,
    product_name            VARCHAR(200),
    variant_name            VARCHAR(200),
    variant_attributes_json JSON,
    image_url               TEXT,
    supplier_name           VARCHAR(200),
    quantity                INT NOT NULL,
    unit_price_cents        INT NOT NULL,
    final_price_cents       INT NOT NULL,
    total_cents             INT NOT NULL,
    fulfillment_status      VARCHAR(20),
    shipped_quantity        INT DEFAULT 0,
    tracking_number         VARCHAR(100),
    carrier                 VARCHAR(100),
    shipped_at              DATETIME(6),
    delivered_at            DATETIME(6),
    UNIQUE KEY uq_order_item (order_id, item_id),
    INDEX idx_items_order (order_id),
    INDEX idx_items_product (product_id),
    CONSTRAINT fk_items_order FOREIGN KEY (order_id)
        REFERENCES orders(order_id) ON DELETE CASCADE
)
```

**Key design decisions:**
- `UNIQUE KEY uq_order_item (order_id, item_id)` — each order can only have one entry per `item_id`. This is the key that the `ON DUPLICATE KEY UPDATE` clause targets for idempotent replays
- `item_id VARCHAR(50)` — not an ObjectId; it's an application-generated item identifier within the order
- Product snapshot fields (`product_name`, `variant_name`, `supplier_name`, etc.) are **frozen at purchase time**. They won't change even if the product is later updated or deleted — this is the point of the snapshot pattern
- `variant_attributes_json JSON` — stores the variant's attribute dict (e.g., `{"size": "small", "color": "white"}`)
- Fulfillment fields (`fulfillment_status`, `shipped_quantity`, `tracking_number`, `carrier`, `shipped_at`, `delivered_at`) are the only fields that change after order creation — they track shipment progress

#### Verify Exercises 5.1 + 5.2

```bash
docker compose restart mysql-service

docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SHOW CREATE TABLE orders\G"
docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SHOW CREATE TABLE order_items\G"
```

**Expected:** Both tables created. `orders` has UNIQUE KEY on `order_number`. `order_items` has composite UNIQUE, FK CASCADE, and JSON column.

---

### Exercise 5.3: Write the DAL Methods (Raw SQL)

**Concept:** Selective upsert (orders), batch insert with selective upsert (items), cancel by business key
**Difficulty:** Very Hard

#### Implement: Three methods in `OrderDAL` in `src/dal/order_dal.py`

> **Don't forget** to add `import json` at the top of `order_dal.py`.

```python
def insert_order(self, order_id, order_number,
                 customer_user_id, customer_display_name,
                 customer_email, customer_phone,
                 shipping_recipient_name, shipping_phone,
                 shipping_street_1, shipping_street_2,
                 shipping_city, shipping_state,
                 shipping_zip_code, shipping_country,
                 status, created_at, updated_at,
                 event_id, event_timestamp):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders
                (order_id, order_number,
                 customer_user_id, customer_display_name,
                 customer_email, customer_phone,
                 shipping_recipient_name, shipping_phone,
                 shipping_street_1, shipping_street_2,
                 shipping_city, shipping_state,
                 shipping_zip_code, shipping_country,
                 status, created_at, updated_at,
                 event_id, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status=VALUES(status),
                updated_at=VALUES(updated_at),
                event_id=VALUES(event_id),
                event_timestamp=VALUES(event_timestamp)
        """, (order_id, order_number,
              customer_user_id, customer_display_name,
              customer_email, customer_phone,
              shipping_recipient_name, shipping_phone,
              shipping_street_1, shipping_street_2,
              shipping_city, shipping_state,
              shipping_zip_code, shipping_country,
              status, created_at, updated_at,
              event_id, event_timestamp))
        cursor.close()
    finally:
        conn.close()

def insert_order_items(self, order_id, items):
    """Batch insert order items.

    Args:
        order_id: The order ID.
        items: List of dicts with item data.
    """
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        for item in items:
            cursor.execute("""
                INSERT INTO order_items
                    (order_id, item_id, product_id, supplier_id,
                     product_name, variant_name, variant_attributes_json,
                     image_url, supplier_name,
                     quantity, unit_price_cents, final_price_cents,
                     total_cents, fulfillment_status, shipped_quantity,
                     tracking_number, carrier, shipped_at, delivered_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    fulfillment_status=VALUES(fulfillment_status),
                    shipped_quantity=VALUES(shipped_quantity),
                    tracking_number=VALUES(tracking_number),
                    carrier=VALUES(carrier),
                    shipped_at=VALUES(shipped_at),
                    delivered_at=VALUES(delivered_at)
            """, (
                order_id,
                item["item_id"],
                item["product_id"],
                item["supplier_id"],
                item["product_name"],
                item.get("variant_name"),
                json.dumps(item.get("variant_attributes", {})),
                item.get("image_url"),
                item.get("supplier_name"),
                item["quantity"],
                item["unit_price_cents"],
                item["final_price_cents"],
                item["total_cents"],
                item.get("fulfillment_status", "pending"),
                item.get("shipped_quantity", 0),
                item.get("tracking_number"),
                item.get("carrier"),
                item.get("shipped_at"),
                item.get("delivered_at"),
            ))
        cursor.close()
    finally:
        conn.close()

def cancel_order(self, order_number, event_id, event_timestamp):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE orders
            SET status = 'cancelled',
                event_id = %s, event_timestamp = %s
            WHERE order_number = %s
        """, (event_id, event_timestamp, order_number))
        cursor.close()
    finally:
        conn.close()
```

**Key design decisions:**

**`insert_order` — Selective upsert:** The ON DUPLICATE KEY UPDATE clause only updates 4 fields: `status`, `updated_at`, `event_id`, `event_timestamp`. All customer and shipping fields are **excluded** because they are immutable snapshots. If the same ORDER_CREATED event replays, the customer info is preserved from the first insert. Contrast this with User/Supplier where nearly all fields are updated on duplicate.

**`insert_order_items` — Selective upsert on children:** Unlike Product variants (which use the replace pattern), order items use `ON DUPLICATE KEY UPDATE` with only fulfillment fields. The product snapshot fields (`product_name`, `variant_name`, etc.) and pricing fields (`quantity`, `unit_price_cents`, etc.) are **never updated** — they are frozen at order creation. Only `fulfillment_status`, `shipped_quantity`, `tracking_number`, `carrier`, `shipped_at`, and `delivered_at` change as the order progresses.

**Why selective upsert instead of replace for items?** Order items have immutable pricing and snapshot data that must be preserved. The replace pattern (DELETE + INSERT) would momentarily remove the rows, which could break concurrent reads and lose the guarantee that pricing data is never modified after order creation.

**`cancel_order` — Update by business key:** Uses `WHERE order_number = %s` instead of `WHERE order_id = %s`. The cancel event payload contains `order_number` (the business-facing identifier), not the MongoDB ObjectId. The `UNIQUE KEY uq_order_number` ensures this WHERE clause matches at most one row.

**`json.dumps()` in the DAL:** `json.dumps(item.get("variant_attributes", {}))` serializes the variant attributes dict. This happens in the DAL (not the consumer) because the consumer passes raw item dicts to the DAL. Compare with Post where `json.dumps()` happens in the consumer.

---

### Exercise 5.4: Write the Consumer Event Handlers

**Concept:** Multi-table writes in one handler, product_snapshot flattening, batch item building
**Difficulty:** Hard

#### Implement: All methods in `OrderConsumer` in `src/consumers/order_consumer.py`

```python
def _parse_ts(self, ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def handle_order_created(self, event: dict):
    data = event.get("data", {})
    customer = data.get("customer", {})
    shipping = data.get("shipping_address", {})

    self._dal.insert_order(
        order_id=event.get("entity_id"),
        order_number=data.get("order_number"),
        customer_user_id=customer.get("user_id"),
        customer_display_name=customer.get("display_name"),
        customer_email=customer.get("email"),
        customer_phone=customer.get("phone"),
        shipping_recipient_name=shipping.get("recipient_name"),
        shipping_phone=shipping.get("phone"),
        shipping_street_1=shipping.get("street_address_1"),
        shipping_street_2=shipping.get("street_address_2"),
        shipping_city=shipping.get("city"),
        shipping_state=shipping.get("state"),
        shipping_zip_code=shipping.get("zip_code"),
        shipping_country=shipping.get("country"),
        status=data.get("status", "pending"),
        created_at=self._parse_ts(data.get("created_at")),
        updated_at=self._parse_ts(data.get("updated_at")),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )

    # Insert order items
    items_data = data.get("items", [])
    items = []
    for item in items_data:
        snapshot = item.get("product_snapshot", {})
        items.append({
            "item_id": item.get("item_id"),
            "product_id": snapshot.get("product_id"),
            "supplier_id": snapshot.get("supplier_id"),
            "product_name": snapshot.get("product_name"),
            "variant_name": snapshot.get("variant_name"),
            "variant_attributes": snapshot.get("variant_attributes", {}),
            "image_url": snapshot.get("image_url"),
            "supplier_name": snapshot.get("supplier_name"),
            "quantity": item.get("quantity"),
            "unit_price_cents": item.get("unit_price_cents"),
            "final_price_cents": item.get("final_price_cents"),
            "total_cents": item.get("total_cents"),
            "fulfillment_status": item.get("fulfillment_status", "pending"),
            "shipped_quantity": item.get("shipped_quantity", 0),
            "tracking_number": item.get("tracking_number"),
            "carrier": item.get("carrier"),
            "shipped_at": self._parse_ts(item.get("shipped_at")),
            "delivered_at": self._parse_ts(item.get("delivered_at")),
        })

    if items:
        self._dal.insert_order_items(event.get("entity_id"), items)

    logger.info(f"[ORDER_CREATED] {event['entity_id']}")

def handle_order_cancelled(self, event: dict):
    data = event.get("data", {})
    self._dal.cancel_order(
        order_number=data.get("order_number"),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )
    logger.info(f"[ORDER_CANCELLED] {event['entity_id']}")

def get_handlers(self) -> dict:
    return {
        EventType.ORDER_CREATED: self.handle_order_created,
        EventType.ORDER_CANCELLED: self.handle_order_cancelled,
    }
```

**Key design decisions:**
- **No shared upsert method** — unlike other domains, Order only has 2 events with completely different handling. `ORDER_CREATED` does multi-table writes; `ORDER_CANCELLED` does a single UPDATE. No code sharing needed
- **Multi-table write in one handler:** `handle_order_created` calls `insert_order()` for the parent row, then `insert_order_items()` for the child rows. Both happen in the same handler invocation
- **Product snapshot flattening:** Each item has a nested `product_snapshot` object. The consumer extracts `snapshot.get("product_id")`, `snapshot.get("product_name")`, etc. into the flat item dict. This is the deepest nesting in the pipeline: `event.data.items[i].product_snapshot.product_name`
- **`data.get("status", "pending")`** — defaults to "pending" if the status field is missing
- **`self._parse_ts(item.get("shipped_at"))`** — timestamps inside each item need parsing too, not just top-level timestamps
- **Cancel uses `order_number`** — the cancel event sends the business key, not the MongoDB ObjectId. The handler passes it directly to the DAL

#### Verify Exercise 5.4

**Step 1: Restart**
```bash
docker compose restart mysql-service
```

**Step 2: Create prerequisites** (user + supplier + product)
```bash
# Create a user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email": "order-buyer@example.com", "password": "Pass123!", "display_name": "Order Buyer"}'
# Save user ID

# Create a supplier
curl -X POST http://localhost:8000/suppliers \
  -H "Content-Type: application/json" \
  -d '{"email": "order-supplier@example.com", "password": "Pass123!", "primary_phone": "+1-555-9999", "legal_name": "Order Test Supplier"}'
# Save supplier ID

# Create a product
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -H "X-Supplier-ID: <supplier-id>" \
  -d '{
    "name": "Order Test Product",
    "category": "home_decor",
    "unit_type": "piece",
    "base_price_cents": 1500,
    "variants": {
      "default": {
        "variant_name": "Default",
        "price_cents": 1500,
        "quantity": 100
      }
    }
  }'
# Save product ID

# Publish the product (must be active to order)
curl -X POST http://localhost:8000/products/<product-id>/publish \
  -H "X-Supplier-ID: <supplier-id>"
```

**Step 3: Create an order**
```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <user-id>" \
  -d '{
    "items": [
      {
        "product_id": "<product-id>",
        "variant_key": "default",
        "quantity": 2
      }
    ],
    "shipping_address": {
      "recipient_name": "Order Buyer",
      "phone": "+1234567890",
      "street_address_1": "789 Pine St",
      "city": "San Francisco",
      "state": "CA",
      "zip_code": "94102",
      "country": "US"
    }
  }'
```

Save the returned `order_number`.

**Step 4: Verify both tables**
```bash
docker compose logs mysql-service | grep ORDER_CREATED

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT order_id, order_number, customer_display_name, status, shipping_city FROM orders\G"

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT order_id, item_id, product_name, quantity, total_cents, fulfillment_status FROM order_items\G"
```

**Expected:** 1 row in `orders` with `status=pending`, 1 row in `order_items` with snapshot data.

**Step 5: Test cancel**
```bash
curl -X POST http://localhost:8000/orders/<order-id>/cancel \
  -H "X-User-ID: <user-id>"

docker compose logs mysql-service | grep ORDER_CANCELLED

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT order_id, order_number, status FROM orders\G"
# status should be "cancelled"

# Order items should still exist (cancel doesn't delete items)
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT COUNT(*) as item_count FROM order_items WHERE order_id = '<order-id>';"
# Should be > 0
```

---

## 6. VERIFICATION CHECKLIST

### Table Checks
- [ ] `SHOW TABLES;` includes `orders` and `order_items`
- [ ] `orders` has UNIQUE KEY `uq_order_number` on `order_number`
- [ ] `order_items` has composite UNIQUE KEY `uq_order_item (order_id, item_id)`
- [ ] `order_items` has FK to `orders` with ON DELETE CASCADE
- [ ] `variant_attributes_json` column type is `json`

### Functional Checks
- [ ] **Create order** -> `[ORDER_CREATED]` in logs -> rows in both tables
- [ ] **Customer snapshot** correct: `customer_display_name`, `customer_email` populated
- [ ] **Shipping address** correct: `shipping_city`, `shipping_state`, `shipping_country` populated
- [ ] **Product snapshot** in items: `product_name`, `variant_name`, `supplier_name` populated
- [ ] **`variant_attributes_json`** contains valid JSON
- [ ] **Pricing fields** correct: `quantity`, `unit_price_cents`, `total_cents`
- [ ] **Cancel order** -> `[ORDER_CANCELLED]` in logs -> `status` changed to `"cancelled"`
- [ ] **Cancel preserves items** — order items still exist after cancellation
- [ ] **Idempotent replay** — processing ORDER_CREATED twice doesn't duplicate the order or items

### Code Quality Checks
- [ ] `import json` present in `order_dal.py`
- [ ] `insert_order` ON DUPLICATE KEY UPDATE only updates `status`, `updated_at`, `event_id`, `event_timestamp`
- [ ] `insert_order_items` ON DUPLICATE KEY UPDATE only updates fulfillment fields
- [ ] `cancel_order` uses `WHERE order_number` (not `WHERE order_id`)
- [ ] `json.dumps()` used for `variant_attributes`
- [ ] `get_handlers()` maps both EventTypes
- [ ] `try/finally` on every DAL method

---

## 7. ADVANCED CHALLENGES

### Challenge A: Order Total via SQL

The `orders` table doesn't store a total. Compute it from `order_items`:

```sql
SELECT o.order_id, o.order_number, o.status,
       SUM(oi.total_cents) as order_total_cents,
       SUM(oi.total_cents) / 100.0 as order_total_dollars,
       COUNT(oi.id) as item_count
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_id, o.order_number, o.status;
```

**Question:** Why compute the total via JOIN instead of storing it on the `orders` row?

**Answer:** Storing a derived total creates a data consistency risk — if item data changes (e.g., fulfillment updates) and the total isn't recalculated, it becomes stale. Computing on-the-fly from the source of truth (item rows) is always consistent. The trade-off is query cost, but for analytics workloads this is acceptable.

### Challenge B: Selective Upsert Comparison

Compare the three different ON DUPLICATE KEY UPDATE strategies used across all tasks:

| Domain | Strategy | What Gets Updated | Why |
|--------|----------|------------------|-----|
| User | **Full upsert** | All fields except PK + created_at | User data changes freely |
| Product | **Full upsert** | All fields except PK + supplier_id + created_at | Product data changes freely |
| Order | **Selective upsert** | Only status + updated_at + event fields | Customer/shipping data is frozen |
| Order Items | **Selective upsert** | Only fulfillment fields | Pricing/snapshot data is frozen |

```sql
-- Verify: update a cancelled order's status back and check customer data
UPDATE orders SET status = 'pending' WHERE order_number = '<order-number>';
-- Customer fields should be unchanged — they were never in the UPDATE clause
```

### Challenge C: CASCADE Delete Test

Test that deleting an order cascades to items:

```sql
-- Count items before
SELECT COUNT(*) FROM order_items WHERE order_id = '<order-id>';

-- Delete the order
DELETE FROM orders WHERE order_id = '<order-id>';

-- Count items after — should be 0
SELECT COUNT(*) FROM order_items WHERE order_id = '<order-id>';
```

Note: The application uses cancel (UPDATE status), not DELETE. CASCADE delete is a safety mechanism in case an order is hard-deleted via admin SQL.

---

## 8. WHAT'S NEXT

Congratulations — you've completed all MySQL analytics consumer tasks. You now understand:

### DDL Skills
- `CREATE TABLE` with `VARCHAR`, `INT`, `DATETIME(6)`, `TEXT`, `JSON`, `DOUBLE`
- `PRIMARY KEY`, `INDEX`, composite `INDEX`, `UNIQUE KEY`, composite `UNIQUE KEY`
- `AUTO_INCREMENT` surrogate keys
- `FOREIGN KEY ... ON DELETE CASCADE`
- `DEFAULT` values for counters and rates
- Table ordering for FK dependencies

### DAL Skills
- `INSERT ... ON DUPLICATE KEY UPDATE` — full upsert, selective upsert
- `UPDATE ... SET ... WHERE` — soft delete, cancel by business key
- `DELETE FROM ... WHERE` — hard delete (parent CASCADE handles children)
- Replace pattern — `DELETE` + batch `INSERT` for child tables
- `json.dumps()` for JSON column serialization
- Connection pool pattern: `get_connection()` / `try/finally` / `conn.close()`

### Consumer Skills
- Kafka event handling with handler registry pattern
- Nested dict traversal with `.get("key", {})` safe access
- ISO 8601 timestamp parsing
- Multi-source flattening (contact_info, company_info, business_address, etc.)
- Dict iteration for child rows (variants)
- List iteration with nested snapshot flattening (order items)
- `json.dumps()` serialization for JSON columns
- Multi-table writes in a single handler

### Architecture Understanding
- Event-driven architecture: MongoDB -> Kafka -> MySQL
- Document-to-relational flattening
- Idempotent event processing via upsert patterns
- Snapshot denormalization (customer, shipping, product data frozen at event time)
- Soft delete vs hard delete design choices
- Parent/child table relationships
- Natural keys (order_number) vs technical keys (order_id)
