# Beanie ODM Guide for MongoDB Developers

You already know MongoDB - queries, documents, collections, indexes, aggregations. **Beanie** is a Python ODM (Object-Document Mapper) that lets you work with MongoDB using Python classes instead of raw dictionaries. Think of it as the MongoDB equivalent of SQLAlchemy for SQL databases.

Instead of writing:
```python
db.collection.insert_one({"email": "jane@example.com", "name": "Jane"})
result = db.collection.find_one({"email": "jane@example.com"})
```

You write:
```python
doc = MyDocument(email="jane@example.com", name="Jane")
await doc.insert()
result = await MyDocument.find_one({"email": "jane@example.com"})
```

The document structure, validation, and type safety are defined once in the class - not scattered across your application.

---

## The Two Building Blocks: Document vs BaseModel

Beanie builds on top of **Pydantic**, Python's data validation library. You need to understand two base classes:

### `BaseModel` (from Pydantic) - Embedded Objects

A `BaseModel` defines a data structure that lives **inside** another document. It does not get its own MongoDB collection. It has no `_id` field and no database methods.

```python
from pydantic import BaseModel

class Address(BaseModel):
    street: str
    city: str
    country: str
```

This is equivalent to a nested object in MongoDB:
```json
{
  "address": {
    "street": "123 Main St",
    "city": "Springfield",
    "country": "US"
  }
}
```

Use `BaseModel` for: nested objects, embedded arrays of objects, snapshots, metadata - anything that doesn't need its own collection.

### `Document` (from Beanie) - Collections

A `Document` maps to a **MongoDB collection**. It automatically gets an `_id` field (as `id`), and has methods for querying, inserting, updating, and deleting.

```python
from beanie import Document

class MyDocument(Document):
    address: Address
    name: str
    created_at: datetime
```

This maps to a MongoDB collection where each document looks like:
```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "address": {
    "street": "123 Main St",
    "city": "Springfield",
    "country": "US"
  },
  "name": "Jane",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Key rule:** Only `Document` classes can interact with the database. `BaseModel` classes are just data containers that ride inside documents.

---

## Initializing Beanie

Before using any Beanie operations, you must initialize it with a database connection and register all your Document models.

```python
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

client = AsyncIOMotorClient("mongodb://localhost:27017")
await init_beanie(
    database=client["my_database"],
    document_models=[DocA, DocB, DocC]  # All Document classes
)
```

**Key points:**
- Beanie uses **Motor**, the async MongoDB driver for Python
- Every `Document` class you want to use must be listed in `document_models`
- This is typically called once during application startup
- After initialization, all Document classes are bound to their collections

In this project, look at `apps/mongo_backend/db/mongo_db.py` to see how initialization works and `apps/mongo_backend/server.py` to see when it's called.

---

## Defining Models

### Field Types and Defaults

Beanie models use standard Python type annotations with Pydantic's `Field` for defaults:

```python
from pydantic import Field
from typing import Optional, List, Dict
from datetime import datetime

class MyDocument(Document):
    title: str                                         # Required string
    subtitle: Optional[str] = None                     # Optional, defaults to None
    count: int                                         # Required integer
    tags: List[str] = Field(default_factory=list)      # Defaults to empty list
    metadata: Dict[str, str] = Field(default_factory=dict)  # Defaults to empty dict
    created_at: datetime = Field(default_factory=utc_now)   # Defaults to current time
    status: str = "draft"                              # Defaults to "draft"
```

**`default_factory`** is used instead of `default` when the default value is mutable (lists, dicts, datetimes). This prevents the shared-mutable-default bug where all instances would share the same list object.

### The Settings Inner Class

The `Settings` class inside a Document configures collection-level options:

```python
class MyDocument(Document):
    title: str
    owner_id: PydanticObjectId
    status: str
    created_at: datetime

    class Settings:
        name = "my_collection"                   # Collection name in MongoDB
        indexes = [
            [("owner_id", 1)],                   # Single-field index
            [("status", 1), ("created_at", -1)], # Compound index
        ]
```

- **`name`**: Sets the MongoDB collection name. Without it, Beanie uses the lowercase class name (e.g., `MyDocument` → `"mydocument"`)
- **`indexes`**: Defines MongoDB indexes. Same syntax as `pymongo` index definitions: `1` for ascending, `-1` for descending

If you've used `db.collection.createIndex()` in the MongoDB shell, this is the equivalent - Beanie creates these indexes when the application starts.

### Nesting BaseModel Inside Document

Documents contain embedded objects by using BaseModel fields:

```python
class Author(BaseModel):
    user_id: PydanticObjectId
    name: str

class Attachment(BaseModel):
    file_type: str
    url: str

class MyDocument(Document):
    author: Author                                     # Single embedded object
    attachments: List[Attachment] = Field(default_factory=list)  # Array of embedded objects
    extra: Optional[SomeModel] = None                  # Optional embedded object
```

This produces MongoDB documents like:
```json
{
  "_id": ObjectId("..."),
  "author": {
    "user_id": ObjectId("..."),
    "name": "Jane"
  },
  "attachments": [
    {"file_type": "image", "url": "https://..."},
    {"file_type": "video", "url": "https://..."}
  ],
  "extra": null
}
```

### PydanticObjectId

MongoDB uses `ObjectId` for `_id` fields. In Beanie, you use `PydanticObjectId` when referencing other documents:

```python
from beanie import PydanticObjectId

class Child(BaseModel):
    parent_id: PydanticObjectId    # References another Document
```

When you receive an ID as a string (e.g., from an API request), convert it:
```python
doc = await MyDocument.get(PydanticObjectId("507f1f77bcf86cd799439011"))
```

### Enums

Use Python enums for fields with a fixed set of values:

```python
from enum import Enum

class Status(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"

class MyDocument(Document):
    status: Status = Status.DRAFT
```

In MongoDB, this stores the string value (`"draft"`, `"active"`, etc.). Inheriting from `str` ensures JSON serialization works correctly.

### Field Validators

Pydantic validators let you enforce business rules on fields:

```python
from pydantic import field_validator

class Profile(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
```

Validators run automatically when a model instance is created or updated. If validation fails, Pydantic raises a `ValidationError`.

---

## Querying Documents

All Beanie query methods are **async** - they return coroutines that must be awaited.

### Fetch by ID: `.get()`

```python
doc = await MyDocument.get(PydanticObjectId(some_id))
```

Equivalent to: `db.collection.findOne({_id: ObjectId("...")})`

Returns the document or `None` if not found.

### Find One: `.find_one()`

```python
doc = await MyDocument.find_one({"some_field": "some_value"})
```

Equivalent to: `db.collection.findOne({"some_field": "some_value"})`

The query syntax is **identical to MongoDB** - you use the same dot notation, operators, and query structure you already know.

### Find Many: `.find()`

```python
docs = await MyDocument.find({"status": "active"}).to_list()
```

Equivalent to: `db.collection.find({status: "active"}).toArray()`

`.find()` returns a query builder. You must call `.to_list()` to execute it and get results.

### Find All: `.find_all()`

```python
docs = await MyDocument.find_all().to_list()
```

Equivalent to: `db.collection.find({}).toArray()`

### Chaining: Sort, Skip, Limit

```python
docs = (
    await MyDocument.find({"status": {"$ne": "deleted"}})
    .sort("-created_at")          # Sort descending by created_at
    .skip(20)                     # Skip first 20 results
    .limit(10)                    # Return at most 10
    .to_list()
)
```

Equivalent to:
```javascript
db.collection.find({status: {$ne: "deleted"}})
    .sort({created_at: -1})
    .skip(20)
    .limit(10)
```

**Sort syntax:** Prefix with `-` for descending. `"-created_at"` = `{created_at: -1}`.

### Using MongoDB Query Operators

Since Beanie passes queries directly to MongoDB, all operators work:

```python
# $in operator
await MyDocument.find({"status": {"$in": ["active", "draft"]}}).to_list()

# $ne operator
await MyDocument.find({"status": {"$ne": "deleted"}}).to_list()

# Dot notation for nested fields
await MyDocument.find({"author.user_id": PydanticObjectId(uid)}).to_list()

# Multiple conditions (implicit AND)
await MyDocument.find({
    "deleted_at": None,
    "published_at": {"$ne": None}
}).to_list()
```

This is the same query language you already know - Beanie just wraps it in Python async methods.

---

## Creating Documents

### Insert a Single Document: `.insert()`

```python
doc = MyDocument(
    title="Hello",
    status="draft"
)
await doc.insert()

# After insert, doc.id is populated with the MongoDB ObjectId
print(doc.id)  # PydanticObjectId("507f1f77bcf86cd799439011")
```

Equivalent to: `db.collection.insertOne({...})`

**Important:** After calling `.insert()`, the document's `id` field is automatically set by MongoDB.

### Insert Many: `.insert_many()`

```python
docs = [
    MyDocument(title="First"),
    MyDocument(title="Second"),
]
await MyDocument.insert_many(docs)
```

Equivalent to: `db.collection.insertMany([...])`

### Building Nested Objects

When creating a document with embedded objects, you construct them from the inside out:

```python
# 1. Build the innermost objects first
address = Address(street="123 Main", city="Springfield", country="US")

# 2. Build mid-level containers
company = CompanyInfo(name="Acme", address=address)

# 3. Build the document
doc = MyDocument(company=company, title="Example")

# 4. Insert
await doc.insert()
```

For deeply nested structures, always build from the leaves up to the root.

---

## Updating Documents

### Modify and Save: `.save()`

The most common pattern is fetch -> modify -> save:

```python
# 1. Fetch the document
doc = await MyDocument.get(PydanticObjectId(some_id))

# 2. Modify fields (including nested ones)
doc.title = "New Title"
doc.address.city = "New City"

# 3. Save back to MongoDB
await doc.save()
```

Equivalent to fetching the document, modifying it, and calling `db.collection.replaceOne({_id: ...}, updatedDoc)`.

**Nested field updates:** You can directly modify fields on embedded objects (`doc.address.city = "..."`) because Beanie tracks the full document and saves the complete state.

### Overriding Save for Auto-Timestamps

A common pattern in this project: override `.save()` to automatically update `updated_at`:

```python
class MyDocument(Document):
    updated_at: datetime = Field(default_factory=utc_now)

    async def save(self, *args, **kwargs):
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
```

Now every call to `await doc.save()` automatically updates the timestamp. The models in this project all follow this pattern.

### Conditional (Partial) Updates

Services often accept optional fields - only update what's provided:

```python
async def update_doc(self, doc_id, field_a=None, field_b=None):
    doc = await self.get_doc(doc_id)

    if field_a is not None:
        doc.field_a = field_a
    if field_b is not None:
        doc.nested.field_b = field_b

    await doc.save()
    return doc
```

The `is not None` check ensures you only overwrite fields that the caller explicitly provided. Fields left as `None` remain unchanged.

---

## Deleting Documents

### Hard Delete: `.delete()`

Permanently removes the document from MongoDB:

```python
doc = await MyDocument.get(PydanticObjectId(some_id))
await doc.delete()
```

Equivalent to: `db.collection.deleteOne({_id: ObjectId("...")})`

The document is gone from the collection.

### Soft Delete Pattern

Instead of removing the document, set a `deleted_at` timestamp:

```python
doc = await MyDocument.get(PydanticObjectId(some_id))
doc.deleted_at = utc_now()
await doc.save()
```

The document stays in MongoDB but is excluded from queries:
```python
# All queries filter out soft-deleted documents
docs = await MyDocument.find({"deleted_at": None}).to_list()
```

**When to use which:**
- **Hard delete**: The entity is completely removed from the database
- **Soft delete**: The entity is logically removed but preserved for audit/recovery

---

## Serialization: `.model_dump()`

To convert a Beanie document to a Python dictionary (e.g., for API responses or Kafka events):

```python
data = doc.model_dump(mode="json")
```

**`mode="json"`** ensures all special types are converted to JSON-serializable formats:
- `ObjectId` -> string
- `datetime` -> ISO 8601 string
- `HttpUrl` -> string
- `Enum` -> value string

**Important:** The `id` field (MongoDB's `_id`) needs manual handling:

```python
data = doc.model_dump(mode="json")
data["id"] = str(doc.id)        # Add string version of ObjectId
data.pop("sensitive_field", None)  # Remove sensitive fields if needed
```

---

## Common Patterns

### Pattern 1: Fetch or 404

A safe way to fetch documents by ID:

```python
async def get_doc(self, doc_id: str) -> MyDocument:
    try:
        doc = await MyDocument.get(PydanticObjectId(doc_id))
    except Exception:
        raise NotFoundError("Not found")
    if not doc:
        raise NotFoundError("Not found")
    return doc
```

**Why the try/except?** If `doc_id` is not a valid 24-character hex string, `PydanticObjectId()` raises an exception. The try/except catches malformed IDs.

For soft-delete models, also check the `deleted_at` field after fetching.

### Pattern 2: Check Uniqueness Before Insert

```python
existing = await MyDocument.find_one({"unique_field": value})
if existing:
    raise DuplicateError("Already exists")
```

Always check for duplicates before inserting, using the field that should be unique.

### Pattern 3: Status Lifecycle

Documents with a status field follow a specific lifecycle. Services enforce valid transitions:

```python
if doc.status != Status.DRAFT:
    raise ValidationError("Only draft items can be published")
doc.status = Status.ACTIVE
await doc.save()
```

### Pattern 4: Denormalized Snapshots

When creating a document that references another, capture a **snapshot** of the referenced data at that moment. The referenced entity might change later, but the snapshot preserves the state at creation time.

```python
# Capture info at creation time, not as a live reference
snapshot = AuthorSnapshot(
    user_id=user.id,
    name=user.profile.display_name,
)
doc = MyDocument(author=snapshot, ...)
await doc.insert()
```

### Pattern 5: Back-References

When two documents reference each other, you manage the relationship manually:

```python
# After creating a child document
parent.child_ids.append(child.id)
await parent.save()

# After deleting a child document
if child.id in parent.child_ids:
    parent.child_ids.remove(child.id)
    await parent.save()
```

### Pattern 6: Emit After Persist

Every mutation follows the same order:

1. Validate inputs
2. Build/modify the document
3. Persist to MongoDB (`insert()` or `save()`)
4. Emit event **after** successful persistence

Never emit an event before the database write succeeds.

---

## Files in This Project

| File | What to Study |
|------|--------------|
| `apps/mongo_backend/db/mongo_db.py` | How Beanie is initialized with Motor |
| `shared/models/*.py` | All 5 Document models and their embedded BaseModels |
| `apps/mongo_backend/services/*.py` | How services use Beanie operations (this is what you implement) |
| `apps/mongo_backend/utils/*.py` | Helper functions for building snapshots and responses |

Read the models first to understand the data structures, then read the services to see how Beanie operations are used against those models.

---

## Quick Reference: Beanie Operations

| Operation | Beanie | MongoDB Shell Equivalent |
|-----------|--------|------------------------|
| Fetch by ID | `await Doc.get(oid)` | `db.col.findOne({_id: oid})` |
| Find one | `await Doc.find_one(query)` | `db.col.findOne(query)` |
| Find many | `await Doc.find(query).to_list()` | `db.col.find(query).toArray()` |
| Find all | `await Doc.find_all().to_list()` | `db.col.find({}).toArray()` |
| Sort | `.sort("-field")` | `.sort({field: -1})` |
| Skip | `.skip(n)` | `.skip(n)` |
| Limit | `.limit(n)` | `.limit(n)` |
| Insert one | `await doc.insert()` | `db.col.insertOne(doc)` |
| Insert many | `await Doc.insert_many(docs)` | `db.col.insertMany(docs)` |
| Update (full) | `await doc.save()` | `db.col.replaceOne({_id}, doc)` |
| Hard delete | `await doc.delete()` | `db.col.deleteOne({_id})` |
| Serialize | `doc.model_dump(mode="json")` | (native in JS) |
| Get ID | `doc.id` | `doc._id` |
