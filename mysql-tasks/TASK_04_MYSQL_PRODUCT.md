# TASK 04: Product - MySQL Analytics Consumer

## 1. MISSION BRIEFING

You are building the **product analytics pipeline** - the first domain that requires **two related tables**. In MongoDB, a product is a single document with variants stored as an embedded dictionary. In MySQL, you split this into a parent `products` table and a child `product_variants` table linked by a foreign key.

This task introduces the most new SQL concepts of any task:
- **Parent/child table design** with FOREIGN KEY ON DELETE CASCADE
- **AUTO_INCREMENT** surrogate key on the child table
- **UNIQUE KEY** composite constraint to prevent duplicate variants
- **JSON column** for semi-structured variant attributes
- **Replace pattern** (DELETE + INSERT) for updating child rows
- **7 event types** - the most of any domain

### What You Will Build

| Layer | File | What You Implement |
|-------|------|--------------------|
| DDL | `src/db/tables.py` | `CREATE TABLE products` (20 cols, 4 indexes) + `CREATE TABLE product_variants` (13 cols, FK, UNIQUE) |
| DAL | `src/dal/product_dal.py` | `upsert_product()` + `replace_variants()` + `delete_product()` |
| Consumer | `src/consumers/product_consumer.py` | 7 event handlers + variant dict iteration |

### What You Will Learn

| SQL Concept | Where You'll Use It |
|-------------|-------------------|
| Parent/child table design | `products` (parent) + `product_variants` (child) |
| `FOREIGN KEY ... ON DELETE CASCADE` | Deleting a product auto-deletes its variants |
| `AUTO_INCREMENT` | Surrogate `id` on `product_variants` (no natural single-column PK) |
| `UNIQUE KEY` (composite) | `(product_id, variant_key)` prevents duplicate variants |
| `JSON` column | `attributes_json` stores variant attribute lists |
| `DOUBLE` column | `width_cm`, `height_cm`, `depth_cm` for dimensions |
| Replace pattern (DELETE + INSERT) | Replacing all variants on every product update |
| `json.dumps()` in Python | Serializing Python lists to JSON strings for the JSON column |

---

## 2. BEFORE YOU START

### Prerequisites
- TASK_01 and TASK_02 completed (User + Supplier working)
- All 5 Docker containers running

### Files You MUST Read Before Coding

#### Step 1: The MongoDB Product Model
```
shared/models/product.py
```
Pay attention to:
- `variants: dict[str, ProductVariant]` — a dictionary keyed by variant name, each value is an embedded document with `variant_id`, `variant_name`, `attributes`, `price_cents`, `cost_cents`, `quantity`, `package_dimensions`, `image_url`
- `metadata: ProductMetadata` → `base_sku`, `brand`
- `stats: ProductStats` → `view_count`, `favorite_count`, `purchase_count`, `total_reviews`
- `supplier_info: SupplierInfo` → `name` (denormalized supplier name)
- Top-level: `supplier_id`, `name`, `short_description`, `category`, `unit_type`, `base_price_cents`, `status`, `published_at`

#### Step 2: The Student Files
```
apps/mysql_server/src/dal/product_dal.py
apps/mysql_server/src/consumers/product_consumer.py
```

#### Step 3: The Kafka Event Types
```
shared/kafka/topics.py
```
The Product domain has **7** event types — the most of any domain:
- `EventType.PRODUCT_CREATED` = `"product.created"`
- `EventType.PRODUCT_UPDATED` = `"product.updated"`
- `EventType.PRODUCT_PUBLISHED` = `"product.published"`
- `EventType.PRODUCT_DISCONTINUED` = `"product.discontinued"`
- `EventType.PRODUCT_OUT_OF_STOCK` = `"product.out_of_stock"`
- `EventType.PRODUCT_RESTORED` = `"product.restored"`
- `EventType.PRODUCT_DELETED` = `"product.deleted"`

All except DELETED send the full product document. DELETED sends a minimal payload.

---

## 3. SCHEMA DEEP DIVE

### Table 1: `products` (Parent)

```
products
├── product_id          VARCHAR(24)   PRIMARY KEY
├── supplier_id         VARCHAR(24)   NOT NULL       ← data.supplier_id
├── supplier_name       VARCHAR(200)                 ← data.supplier_info.name
├── name                VARCHAR(200)  NOT NULL       ← data.name
├── short_description   VARCHAR(500)                 ← data.short_description
├── category            VARCHAR(50)   NOT NULL       ← data.category
├── unit_type           VARCHAR(20)   NOT NULL       ← data.unit_type
├── base_sku            VARCHAR(100)                 ← data.metadata.base_sku
├── brand               VARCHAR(100)                 ← data.metadata.brand
├── base_price_cents    INT           NOT NULL       ← data.base_price_cents
├── status              VARCHAR(20)   NOT NULL       ← data.status
├── view_count          INT           DEFAULT 0      ← data.stats.view_count
├── favorite_count      INT           DEFAULT 0      ← data.stats.favorite_count
├── purchase_count      INT           DEFAULT 0      ← data.stats.purchase_count
├── total_reviews       INT           DEFAULT 0      ← data.stats.total_reviews
├── published_at        DATETIME(6)                  ← data.published_at
├── created_at          DATETIME(6)   NOT NULL
├── updated_at          DATETIME(6)   NOT NULL
├── event_id            VARCHAR(36)
├── event_timestamp     DATETIME(6)
│
├── INDEX idx_products_supplier (supplier_id)
├── INDEX idx_products_category (category)
├── INDEX idx_products_status (status)
└── INDEX idx_products_created (created_at)
```

### Table 2: `product_variants` (Child)

```
product_variants
├── id              INT           AUTO_INCREMENT PRIMARY KEY   ← surrogate key
├── product_id      VARCHAR(24)   NOT NULL                     ← parent FK
├── variant_key     VARCHAR(200)  NOT NULL                     ← dict key from MongoDB
├── variant_id      VARCHAR(100)  NOT NULL                     ← variant.variant_id
├── variant_name    VARCHAR(200)  NOT NULL                     ← variant.variant_name
├── attributes_json JSON                                       ← variant.attributes (serialized)
├── price_cents     INT           NOT NULL                     ← variant.price_cents
├── cost_cents      INT                                        ← variant.cost_cents
├── quantity        INT           DEFAULT 0                    ← variant.quantity
├── width_cm        DOUBLE                                     ← variant.package_dimensions.width_cm
├── height_cm       DOUBLE                                     ← variant.package_dimensions.height_cm
├── depth_cm        DOUBLE                                     ← variant.package_dimensions.depth_cm
├── image_url       TEXT                                       ← variant.image_url
│
├── UNIQUE KEY uq_product_variant (product_id, variant_key)
├── INDEX idx_variants_product (product_id)
└── CONSTRAINT fk_variants_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE CASCADE
```

### Why Two Tables?

In MongoDB, variants are a dict embedded inside the product document:
```json
{
  "variants": {
    "small-red": { "variant_name": "Small Red", "price_cents": 1500, ... },
    "large-blue": { "variant_name": "Large Blue", "price_cents": 2000, ... }
  }
}
```

In MySQL, you can't store a variable number of structured objects in a single row. The relational approach is a **child table** where each variant becomes its own row, linked to the parent product by `product_id`.

### Key Constraints Explained

| Constraint | Purpose |
|-----------|---------|
| `AUTO_INCREMENT PRIMARY KEY` | Gives each variant row a unique integer ID. Needed because there's no natural single-column PK — the uniqueness comes from the combination of `product_id` + `variant_key` |
| `UNIQUE KEY (product_id, variant_key)` | Prevents two rows with the same product and variant key. This is the **logical** primary key |
| `FOREIGN KEY ... ON DELETE CASCADE` | When you `DELETE FROM products WHERE product_id = X`, MySQL automatically deletes all rows in `product_variants` where `product_id = X`. No orphaned child rows |
| `JSON` column | `attributes_json` stores a list of attribute objects (e.g., `[{"name": "color", "value": "red"}]`). Using JSON avoids creating yet another child table for a semi-structured list |

---

## 4. THE FLATTENING MAP

### Products Table

```
MongoDB Document (nested)                    MySQL Column (flat)
===========================                  ===================

event.entity_id ───────────────────────────> product_id
data.supplier_id ──────────────────────────> supplier_id
data.supplier_info.name ───────────────────> supplier_name
data.name ─────────────────────────────────> name
data.short_description ────────────────────> short_description
data.category ─────────────────────────────> category
data.unit_type ────────────────────────────> unit_type

data.metadata ──────┐
  .base_sku ────────┼─────────────────────> base_sku
  .brand ───────────┘─────────────────────> brand

data.base_price_cents ─────────────────────> base_price_cents
data.status ───────────────────────────────> status

data.stats ─────────┐
  .view_count ──────┼─────────────────────> view_count
  .favorite_count ──┼─────────────────────> favorite_count
  .purchase_count ──┼─────────────────────> purchase_count
  .total_reviews ───┘─────────────────────> total_reviews

data.published_at ─────────────────────────> published_at
data.created_at ───────────────────────────> created_at
data.updated_at ───────────────────────────> updated_at
event.event_id ────────────────────────────> event_id
event.timestamp ───────────────────────────> event_timestamp
```

### Product Variants Table

For each key-value pair in `data.variants`:

```
MongoDB Variant (nested in dict)             MySQL Column (flat)
================================             ===================

(dict key) ────────────────────────────────> variant_key
variant.variant_id ────────────────────────> variant_id
variant.variant_name ──────────────────────> variant_name
json.dumps(variant.attributes) ────────────> attributes_json
variant.price_cents ───────────────────────> price_cents
variant.cost_cents ────────────────────────> cost_cents
variant.quantity ──────────────────────────> quantity

variant.package_dimensions ──┐
  .width_cm ────────────────┼─────────────> width_cm
  .height_cm ───────────────┼─────────────> height_cm
  .depth_cm ────────────────┘─────────────> depth_cm

variant.image_url ─────────────────────────> image_url
```

### The Event Payload (PRODUCT_CREATED / all non-delete events)

```json
{
  "event_type": "product.created",
  "event_id": "uuid-string",
  "entity_id": "abc123def456abc123def456",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": {
    "supplier_id": "60a7b2c3d4e5f6a7b8c9d0e1",
    "supplier_info": { "name": "Acme Corp" },
    "name": "Handmade Ceramic Mug",
    "short_description": "Beautiful handcrafted mug",
    "category": "home_decor",
    "unit_type": "piece",
    "metadata": {
      "base_sku": "MUG-001",
      "brand": "Acme Ceramics"
    },
    "base_price_cents": 2500,
    "status": "draft",
    "stats": {
      "view_count": 0,
      "favorite_count": 0,
      "purchase_count": 0,
      "total_reviews": 0
    },
    "variants": {
      "small-white": {
        "variant_id": "var-001",
        "variant_name": "Small White",
        "attributes": [{"name": "size", "value": "small"}, {"name": "color", "value": "white"}],
        "price_cents": 2500,
        "cost_cents": 800,
        "quantity": 50,
        "package_dimensions": { "width_cm": 10.0, "height_cm": 12.0, "depth_cm": 10.0 },
        "image_url": "https://cdn.example.com/mug-small-white.jpg"
      },
      "large-blue": {
        "variant_id": "var-002",
        "variant_name": "Large Blue",
        "attributes": [{"name": "size", "value": "large"}, {"name": "color", "value": "blue"}],
        "price_cents": 3500,
        "cost_cents": 1200,
        "quantity": 25,
        "package_dimensions": { "width_cm": 12.0, "height_cm": 14.0, "depth_cm": 12.0 },
        "image_url": "https://cdn.example.com/mug-large-blue.jpg"
      }
    },
    "published_at": null,
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  }
}
```

**PRODUCT_DELETED** (minimal payload):
```json
{
  "event_type": "product.deleted",
  "event_id": "uuid-string",
  "entity_id": "abc123def456abc123def456",
  "timestamp": "2025-01-15T12:00:00Z",
  "data": {
    "product_id": "abc123def456abc123def456"
  }
}
```

---

## 5. IMPLEMENTATION EXERCISES

---

### Exercise 5.1: Define the `products` Table (DDL)

**Concept:** Parent table with 20 columns, 4 indexes, DEFAULT values for stats counters
**Difficulty:** Medium

#### Implement: Add the `products` table DDL to `TABLE_DEFINITIONS` in `src/db/tables.py`

Append this after the `suppliers` table definition:

```sql
CREATE TABLE IF NOT EXISTS products (
    product_id          VARCHAR(24) PRIMARY KEY,
    supplier_id         VARCHAR(24) NOT NULL,
    supplier_name       VARCHAR(200),
    name                VARCHAR(200) NOT NULL,
    short_description   VARCHAR(500),
    category            VARCHAR(50) NOT NULL,
    unit_type           VARCHAR(20) NOT NULL,
    base_sku            VARCHAR(100),
    brand               VARCHAR(100),
    base_price_cents    INT NOT NULL,
    status              VARCHAR(20) NOT NULL,
    view_count          INT DEFAULT 0,
    favorite_count      INT DEFAULT 0,
    purchase_count      INT DEFAULT 0,
    total_reviews       INT DEFAULT 0,
    published_at        DATETIME(6),
    created_at          DATETIME(6) NOT NULL,
    updated_at          DATETIME(6) NOT NULL,
    event_id            VARCHAR(36),
    event_timestamp     DATETIME(6),
    INDEX idx_products_supplier (supplier_id),
    INDEX idx_products_category (category),
    INDEX idx_products_status (status),
    INDEX idx_products_created (created_at)
)
```

**Key design decisions:**
- `base_price_cents INT NOT NULL` — prices stored as integers (cents) to avoid floating-point rounding. $25.00 = 2500
- `status VARCHAR(20)` — stores the enum string directly (`"draft"`, `"active"`, `"discontinued"`, `"out_of_stock"`)
- All 4 stat counters default to 0 — a freshly created product has no views, favorites, purchases, or reviews
- `supplier_id` is NOT NULL but has no FK to the `suppliers` table — this is intentional. The supplier may not yet exist in the MySQL replica (events arrive out of order), and we don't want to reject product events because of a missing supplier

---

### Exercise 5.2: Define the `product_variants` Table (DDL)

**Concept:** Child table with AUTO_INCREMENT, FOREIGN KEY ON DELETE CASCADE, UNIQUE composite key, JSON column
**Difficulty:** Hard

#### Implement: Add the `product_variants` table DDL to `TABLE_DEFINITIONS`

This **must** come after the `products` table definition (the FK references `products`):

```sql
CREATE TABLE IF NOT EXISTS product_variants (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    product_id      VARCHAR(24) NOT NULL,
    variant_key     VARCHAR(200) NOT NULL,
    variant_id      VARCHAR(100) NOT NULL,
    variant_name    VARCHAR(200) NOT NULL,
    attributes_json JSON,
    price_cents     INT NOT NULL,
    cost_cents      INT,
    quantity         INT DEFAULT 0,
    width_cm        DOUBLE,
    height_cm       DOUBLE,
    depth_cm        DOUBLE,
    image_url       TEXT,
    UNIQUE KEY uq_product_variant (product_id, variant_key),
    INDEX idx_variants_product (product_id),
    CONSTRAINT fk_variants_product FOREIGN KEY (product_id)
        REFERENCES products(product_id) ON DELETE CASCADE
)
```

**Key design decisions:**
- `id INT AUTO_INCREMENT PRIMARY KEY` — surrogate key because the natural key is composite (`product_id` + `variant_key`). AUTO_INCREMENT generates unique integers automatically
- `UNIQUE KEY uq_product_variant (product_id, variant_key)` — enforces that each product can only have one variant with a given key (e.g., one "small-red" per product)
- `FOREIGN KEY ... ON DELETE CASCADE` — when a product row is deleted, all its variant rows are automatically deleted. This prevents orphaned variants and simplifies the delete handler
- `attributes_json JSON` — variant attributes are a list of `{name, value}` objects. Using a JSON column avoids a third table and preserves the semi-structured nature of the data
- `DOUBLE` for dimensions — floating-point values for centimeter measurements
- **Table ordering matters:** this DDL must execute after the `products` table DDL, because the FK references `products(product_id)`

#### Verify Exercises 5.1 + 5.2

```bash
docker compose restart mysql-service

docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SHOW CREATE TABLE products\G"
docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SHOW CREATE TABLE product_variants\G"
```

**Expected:** Both tables created. `product_variants` shows the FK constraint and UNIQUE key.

---

### Exercise 5.3: Write the DAL Methods (Raw SQL)

**Concept:** Upsert for parent, replace pattern (DELETE + INSERT) for children, hard delete for parent
**Difficulty:** Hard

#### Implement: Three methods in `ProductDAL` in `src/dal/product_dal.py`

```python
def upsert_product(self, product_id, supplier_id, supplier_name,
                   name, short_description, category, unit_type,
                   base_sku, brand, base_price_cents, status,
                   view_count, favorite_count, purchase_count,
                   total_reviews, published_at, created_at, updated_at,
                   event_id, event_timestamp):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products
                (product_id, supplier_id, supplier_name,
                 name, short_description, category, unit_type,
                 base_sku, brand, base_price_cents, status,
                 view_count, favorite_count, purchase_count,
                 total_reviews, published_at, created_at, updated_at,
                 event_id, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                supplier_name=VALUES(supplier_name),
                name=VALUES(name),
                short_description=VALUES(short_description),
                category=VALUES(category), unit_type=VALUES(unit_type),
                base_sku=VALUES(base_sku), brand=VALUES(brand),
                base_price_cents=VALUES(base_price_cents),
                status=VALUES(status),
                view_count=VALUES(view_count),
                favorite_count=VALUES(favorite_count),
                purchase_count=VALUES(purchase_count),
                total_reviews=VALUES(total_reviews),
                published_at=VALUES(published_at),
                updated_at=VALUES(updated_at),
                event_id=VALUES(event_id),
                event_timestamp=VALUES(event_timestamp)
        """, (product_id, supplier_id, supplier_name,
              name, short_description, category, unit_type,
              base_sku, brand, base_price_cents, status,
              view_count, favorite_count, purchase_count,
              total_reviews, published_at, created_at, updated_at,
              event_id, event_timestamp))
        cursor.close()
    finally:
        conn.close()

def replace_variants(self, product_id, variants):
    """Delete existing variants and insert new ones.

    Args:
        product_id: The product ID.
        variants: List of dicts with variant data.
    """
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM product_variants WHERE product_id = %s",
            (product_id,),
        )
        for v in variants:
            cursor.execute("""
                INSERT INTO product_variants
                    (product_id, variant_key, variant_id, variant_name,
                     attributes_json, price_cents, cost_cents, quantity,
                     width_cm, height_cm, depth_cm, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                product_id,
                v["variant_key"],
                v["variant_id"],
                v["variant_name"],
                json.dumps(v["attributes"]),
                v["price_cents"],
                v.get("cost_cents"),
                v.get("quantity", 0),
                v.get("width_cm"),
                v.get("height_cm"),
                v.get("depth_cm"),
                v.get("image_url"),
            ))
        cursor.close()
    finally:
        conn.close()

def delete_product(self, product_id):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE product_id = %s",
                       (product_id,))
        cursor.close()
    finally:
        conn.close()
```

> **Don't forget** to add `import json` at the top of `product_dal.py`.

**Key design decisions:**
- `upsert_product` — same ON DUPLICATE KEY UPDATE pattern. Skips `product_id` (PK), `supplier_id` (immutable - product doesn't change supplier), and `created_at` (immutable)
- `replace_variants` — the **replace pattern**: DELETE all existing variants for this product, then INSERT the new set. This is simpler than trying to diff which variants changed, were added, or removed. The trade-off is slightly more write I/O, but correctness is guaranteed
- `json.dumps(v["attributes"])` — serializes the Python list `[{"name": "color", "value": "red"}]` to a JSON string for the `JSON` column
- `delete_product` — hard DELETE on the parent row. The `ON DELETE CASCADE` constraint automatically deletes all variant child rows. You don't need to explicitly delete variants
- `replace_variants` uses `v["variant_key"]` (bracket notation) for required fields and `v.get("cost_cents")` (get with None default) for optional fields

#### Verify Exercise 5.3

```bash
docker compose restart mysql-service
docker compose logs mysql-service | tail -10
# No import errors
```

---

### Exercise 5.4: Write the Consumer Event Handlers

**Concept:** 7 event handlers, variant dict iteration, shared upsert method
**Difficulty:** Medium-Hard

#### Implement: All methods in `ProductConsumer` in `src/consumers/product_consumer.py`

```python
def _parse_ts(self, ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def _handle_product_upsert(self, event: dict):
    """Shared handler for all events that send full product model."""
    data = event.get("data", {})
    metadata = data.get("metadata", {})
    stats = data.get("stats", {})
    supplier_info = data.get("supplier_info", {})

    self._dal.upsert_product(
        product_id=event.get("entity_id"),
        supplier_id=data.get("supplier_id"),
        supplier_name=supplier_info.get("name"),
        name=data.get("name"),
        short_description=data.get("short_description"),
        category=data.get("category"),
        unit_type=data.get("unit_type"),
        base_sku=metadata.get("base_sku"),
        brand=metadata.get("brand"),
        base_price_cents=data.get("base_price_cents"),
        status=data.get("status"),
        view_count=stats.get("view_count", 0),
        favorite_count=stats.get("favorite_count", 0),
        purchase_count=stats.get("purchase_count", 0),
        total_reviews=stats.get("total_reviews", 0),
        published_at=self._parse_ts(data.get("published_at")),
        created_at=self._parse_ts(data.get("created_at")),
        updated_at=self._parse_ts(data.get("updated_at")),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )

    # Replace variants
    variants_dict = data.get("variants", {})
    variants = []
    for key, v in variants_dict.items():
        dims = v.get("package_dimensions", {})
        variants.append({
            "variant_key": key,
            "variant_id": v.get("variant_id"),
            "variant_name": v.get("variant_name"),
            "attributes": v.get("attributes", []),
            "price_cents": v.get("price_cents"),
            "cost_cents": v.get("cost_cents"),
            "quantity": v.get("quantity", 0),
            "width_cm": dims.get("width_cm"),
            "height_cm": dims.get("height_cm"),
            "depth_cm": dims.get("depth_cm"),
            "image_url": v.get("image_url"),
        })

    if variants:
        self._dal.replace_variants(event.get("entity_id"), variants)

def handle_product_created(self, event: dict):
    self._handle_product_upsert(event)
    logger.info(f"[PRODUCT_CREATED] {event['entity_id']}")

def handle_product_updated(self, event: dict):
    self._handle_product_upsert(event)
    logger.info(f"[PRODUCT_UPDATED] {event['entity_id']}")

def handle_product_published(self, event: dict):
    self._handle_product_upsert(event)
    logger.info(f"[PRODUCT_PUBLISHED] {event['entity_id']}")

def handle_product_discontinued(self, event: dict):
    self._handle_product_upsert(event)
    logger.info(f"[PRODUCT_DISCONTINUED] {event['entity_id']}")

def handle_product_out_of_stock(self, event: dict):
    self._handle_product_upsert(event)
    logger.info(f"[PRODUCT_OUT_OF_STOCK] {event['entity_id']}")

def handle_product_restored(self, event: dict):
    self._handle_product_upsert(event)
    logger.info(f"[PRODUCT_RESTORED] {event['entity_id']}")

def handle_product_deleted(self, event: dict):
    data = event.get("data", {})
    self._dal.delete_product(
        product_id=data.get("product_id") or event.get("entity_id"),
    )
    logger.info(f"[PRODUCT_DELETED] {event['entity_id']}")

def get_handlers(self) -> dict:
    return {
        EventType.PRODUCT_CREATED: self.handle_product_created,
        EventType.PRODUCT_UPDATED: self.handle_product_updated,
        EventType.PRODUCT_PUBLISHED: self.handle_product_published,
        EventType.PRODUCT_DISCONTINUED: self.handle_product_discontinued,
        EventType.PRODUCT_OUT_OF_STOCK: self.handle_product_out_of_stock,
        EventType.PRODUCT_RESTORED: self.handle_product_restored,
        EventType.PRODUCT_DELETED: self.handle_product_deleted,
    }
```

**Key design decisions:**
- `_handle_product_upsert` handles **6 out of 7** event types. All lifecycle events (created, updated, published, discontinued, out_of_stock, restored) send the full product document. Only the upserted data (like `status`) differs between them — the shared handler processes them identically
- **Variant dict iteration:** `for key, v in variants_dict.items()` — the MongoDB document stores variants as a dict keyed by variant name (e.g., `"small-red"`). The `key` becomes `variant_key` in the child table
- `dims = v.get("package_dimensions", {})` — dimensions are nested one level deeper inside each variant
- `if variants:` — only call `replace_variants` if there are variants. A product with no variants skips the child table write entirely
- `stats.get("view_count", 0)` — default to 0 for missing stat values (newly created products may not have stats)

#### Verify Exercise 5.4

**Step 1: Restart**
```bash
docker compose restart mysql-service
```

**Step 2: Create a product** (requires a supplier to exist first)
```bash
# Create a supplier first (if you don't have one)
curl -X POST http://localhost:8000/suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "email": "product-test-supplier@example.com",
    "password": "Pass123!",
    "primary_phone": "+1-555-0100",
    "legal_name": "Product Test Supplier"
  }'
# Save the supplier ID

# Create a product
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -H "X-Supplier-ID: <supplier-id>" \
  -d '{
    "name": "Analytics Test Mug",
    "short_description": "A mug for testing analytics",
    "category": "home_decor",
    "unit_type": "piece",
    "base_price_cents": 2500,
    "variants": {
      "small-white": {
        "variant_name": "Small White",
        "price_cents": 2500,
        "quantity": 50,
        "attributes": [{"name": "size", "value": "small"}]
      },
      "large-blue": {
        "variant_name": "Large Blue",
        "price_cents": 3500,
        "quantity": 25,
        "attributes": [{"name": "size", "value": "large"}]
      }
    }
  }'
```

Save the returned product `id`.

**Step 3: Check both tables**
```bash
docker compose logs mysql-service | grep PRODUCT_CREATED

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT product_id, name, status, base_price_cents FROM products\G"

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT product_id, variant_key, variant_name, price_cents, attributes_json FROM product_variants\G"
```

**Expected:** 1 row in `products`, 2 rows in `product_variants`.

**Step 4: Test CASCADE delete**
```bash
curl -X DELETE http://localhost:8000/products/<product-id> \
  -H "X-Supplier-ID: <supplier-id>"

docker compose logs mysql-service | grep PRODUCT_DELETED

# Both parent and child rows should be gone
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT COUNT(*) as products FROM products WHERE product_id = '<product-id>';"
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT COUNT(*) as variants FROM product_variants WHERE product_id = '<product-id>';"
# Both should be 0 — CASCADE deleted the variants automatically
```

---

## 6. VERIFICATION CHECKLIST

### Table Checks
- [ ] `SHOW TABLES;` includes `products` and `product_variants`
- [ ] `products` has 20 columns and 4 indexes
- [ ] `product_variants` has AUTO_INCREMENT, UNIQUE KEY, FOREIGN KEY
- [ ] `SHOW CREATE TABLE product_variants\G` shows `ON DELETE CASCADE`

### Functional Checks
- [ ] **Create product** -> `[PRODUCT_CREATED]` in logs -> rows in both tables
- [ ] **Variant rows** have correct `variant_key`, `variant_name`, `price_cents`
- [ ] **`attributes_json`** contains valid JSON (e.g., `[{"name": "size", "value": "small"}]`)
- [ ] **Publish product** -> `[PRODUCT_PUBLISHED]` in logs -> `status` updated to `"active"` in MySQL
- [ ] **Delete product** -> `[PRODUCT_DELETED]` in logs -> product row AND all variant rows removed (CASCADE)
- [ ] **Variant replacement** works: update product -> old variants deleted, new variants inserted

### Code Quality Checks
- [ ] `import json` present in `product_dal.py`
- [ ] `json.dumps()` used for `attributes` -> `attributes_json`
- [ ] `replace_variants` DELETEs before INSERTing (replace pattern)
- [ ] `delete_product` only deletes the parent row (CASCADE handles children)
- [ ] `get_handlers()` maps all 7 EventTypes
- [ ] `try/finally` on every DAL method

---

## 7. ADVANCED CHALLENGES

### Challenge A: CASCADE in Action

Verify that ON DELETE CASCADE works by inserting test data and observing the cascade:

```sql
-- Insert a test product directly
INSERT INTO products (product_id, supplier_id, name, category, unit_type,
    base_price_cents, status, created_at, updated_at)
VALUES ('test_cascade_product_1', 'test_supplier', 'Cascade Test', 'test',
    'piece', 100, 'draft', NOW(6), NOW(6));

-- Insert two variants
INSERT INTO product_variants (product_id, variant_key, variant_id, variant_name, price_cents)
VALUES ('test_cascade_product_1', 'v1', 'vid1', 'Variant 1', 100);
INSERT INTO product_variants (product_id, variant_key, variant_id, variant_name, price_cents)
VALUES ('test_cascade_product_1', 'v2', 'vid2', 'Variant 2', 200);

-- Verify: 2 variants exist
SELECT COUNT(*) FROM product_variants WHERE product_id = 'test_cascade_product_1';

-- Delete the parent
DELETE FROM products WHERE product_id = 'test_cascade_product_1';

-- Verify: variants are gone too (CASCADE)
SELECT COUNT(*) FROM product_variants WHERE product_id = 'test_cascade_product_1';
-- Should be 0
```

### Challenge B: Why Replace Instead of Upsert for Variants?

The `replace_variants` method DELETEs all variants and re-INSERTs them. Why not use `INSERT ... ON DUPLICATE KEY UPDATE` like the parent table?

**Answer:** The replace pattern handles three cases that upsert doesn't handle cleanly:
1. **Removed variants** — if a product had variants `["small", "medium", "large"]` and is updated to `["small", "large"]`, the DELETE removes `"medium"`. With upsert, the old `"medium"` row would remain as an orphan.
2. **Renamed keys** — if `"small-red"` is renamed to `"small-crimson"`, the old key remains with upsert but is cleaned up with replace.
3. **Simplicity** — replace is a single mental model: "the variants in MySQL always mirror the variants in MongoDB." No diffing logic needed.

The trade-off is that every product event causes a DELETE + N INSERTs on the variants table, even if nothing changed. For an analytics replica this is acceptable.

---

## 8. WHAT'S NEXT

You've handled the most complex table structure in this track. You now understand:
- Parent/child table design with FOREIGN KEY ON DELETE CASCADE
- AUTO_INCREMENT surrogate keys
- Composite UNIQUE KEY constraints
- JSON columns for semi-structured data
- The replace pattern (DELETE + INSERT) for child table updates
- Multiple event types handled by a single shared method

**TASK 05: Post** brings a different kind of complexity:
- **JSON column for media arrays** — `media_json` stores serialized media attachment lists
- **DOUBLE type** for `engagement_rate`
- **Compound indexes** for different query patterns
- **`json.dumps()` in the consumer** (not just the DAL)
- **Link preview flattening** — an optional nested object spread across 4 columns
- Soft delete (like User) instead of hard delete (like Product)

The parent/child challenge is behind you. Post is a single-table domain, but with richer data types.
