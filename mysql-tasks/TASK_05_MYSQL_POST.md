# TASK 05: Post - MySQL Analytics Consumer

## 1. MISSION BRIEFING

You are building the **post analytics pipeline**. Posts are the social content of the platform — text updates, media shares, and link previews created by users. The MongoDB post document contains a denormalized author snapshot, an array of media attachments, an optional link preview object, and engagement statistics.

This task introduces:
- **JSON column for arrays** — serializing a Python list of media attachments into a MySQL JSON column
- **DOUBLE type** — floating-point `engagement_rate` for analytics
- **`json.dumps()` in the consumer** — the consumer itself serializes data before passing it to the DAL
- **Link preview flattening** — an optional nested object spread across 4 separate columns
- **Soft delete** — same pattern as User (UPDATE, not DELETE)

### What You Will Build

| Layer | File | What You Implement |
|-------|------|--------------------|
| DDL | `src/db/tables.py` | `CREATE TABLE posts` with 26 columns, 4 indexes |
| DAL | `src/dal/post_dal.py` | `upsert_post()` (26-param) + `soft_delete_post()` |
| Consumer | `src/consumers/post_consumer.py` | 4 event handlers with `json.dumps()` for media |

### What You Will Learn

| SQL Concept | Where You'll Use It |
|-------------|-------------------|
| `JSON` column for arrays | `media_json` stores serialized media attachment list |
| `DOUBLE DEFAULT 0.0` | `engagement_rate` for floating-point engagement metrics |
| 26-parameter upsert | Large INSERT ON DUPLICATE KEY UPDATE |
| Compound indexes | 4 indexes for different analytics query patterns |
| `json.dumps()` in consumer | Serializing Python lists to JSON strings before the DAL |
| Optional object flattening | `link_preview` → 4 separate columns (may be null entirely) |

---

## 2. BEFORE YOU START

### Prerequisites
- TASK_01, TASK_02, and TASK_04 completed
- All 5 Docker containers running

### Files You MUST Read Before Coding

#### Step 1: The MongoDB Post Model
```
shared/models/post.py
```
Pay attention to:
- `PostAuthor` embedded document: `user_id`, `display_name`, `avatar`, `author_type`
- `MediaAttachment` embedded document: `media_type`, `url`, `thumbnail_url`, `alt_text`, etc.
- `LinkPreview` embedded document: `url`, `title`, `description`, `image`, `site_name`
- `PostStats` embedded document: `view_count`, `like_count`, `comment_count`, `share_count`, `save_count`, `engagement_rate`, `last_comment_at`
- `media: list[MediaAttachment]` — a list (not a dict like Product variants)
- `link_preview: Optional[LinkPreview]` — may be `None` entirely

#### Step 2: The Student Files
```
apps/mysql_server/src/dal/post_dal.py
apps/mysql_server/src/consumers/post_consumer.py
```

#### Step 3: The Kafka Event Types
```
shared/kafka/topics.py
```
The Post domain has 4 event types:
- `EventType.POST_CREATED` = `"post.created"`
- `EventType.POST_UPDATED` = `"post.updated"`
- `EventType.POST_PUBLISHED` = `"post.published"`
- `EventType.POST_DELETED` = `"post.deleted"`

---

## 3. SCHEMA DEEP DIVE

### The Target: `posts` Table

```
posts
├── post_id             VARCHAR(24)   PRIMARY KEY
├── post_type           VARCHAR(20)   NOT NULL       ← data.post_type
├── author_user_id      VARCHAR(24)   NOT NULL       ← data.author.user_id
├── author_display_name VARCHAR(200)                 ← data.author.display_name
├── author_avatar       TEXT                         ← data.author.avatar
├── author_type         VARCHAR(20)                  ← data.author.author_type
├── text_content        TEXT                         ← data.text_content
├── media_json          JSON                         ← json.dumps(data.media)
├── link_url            TEXT                         ← data.link_preview.url
├── link_title          VARCHAR(200)                 ← data.link_preview.title
├── link_description    VARCHAR(500)                 ← data.link_preview.description
├── link_image          TEXT                         ← data.link_preview.image
├── link_site_name      VARCHAR(200)                 ← data.link_preview.site_name
├── view_count          INT           DEFAULT 0      ← data.stats.view_count
├── like_count          INT           DEFAULT 0      ← data.stats.like_count
├── comment_count       INT           DEFAULT 0      ← data.stats.comment_count
├── share_count         INT           DEFAULT 0      ← data.stats.share_count
├── save_count          INT           DEFAULT 0      ← data.stats.save_count
├── engagement_rate     DOUBLE        DEFAULT 0.0    ← data.stats.engagement_rate
├── last_comment_at     DATETIME(6)                  ← data.stats.last_comment_at
├── deleted_at          DATETIME(6)                  ← data.deleted_at (soft delete)
├── published_at        DATETIME(6)                  ← data.published_at
├── created_at          DATETIME(6)   NOT NULL
├── updated_at          DATETIME(6)   NOT NULL
├── event_id            VARCHAR(36)
├── event_timestamp     DATETIME(6)
│
├── INDEX idx_posts_author (author_user_id)
├── INDEX idx_posts_type (post_type)
├── INDEX idx_posts_published (published_at)
└── INDEX idx_posts_created (created_at)
```

### Column Groups Explained

**Author snapshot (4 columns):** The MongoDB post stores a denormalized copy of the author's info at the time of posting. This means `author_display_name` may differ from the user's current `display_name` in the `users` table — and that's intentional. It captures how the author appeared when the post was created.

**Media (1 JSON column):** Media attachments are a variable-length list of objects. Rather than creating a child table (like we did for product variants), we store the entire list as a JSON string. This is appropriate because: (1) we don't need to query individual media items, (2) we only need the list for display, and (3) the list is typically small (1-5 items).

**Link preview (5 columns):** The link preview is an optional object. When present, its 5 fields are spread across 5 columns. When absent, all 5 columns are NULL. This is simpler than a child table because there's at most one link preview per post.

**Engagement stats (7 columns):** All counter fields default to 0. `engagement_rate` is the only `DOUBLE` in the schema — it's a computed ratio that uses floating-point precision.

---

## 4. THE FLATTENING MAP

```
MongoDB Document (nested)                    MySQL Column (flat)
===========================                  ===================

event.entity_id ───────────────────────────> post_id
data.post_type ────────────────────────────> post_type

data.author ────────┐
  .user_id ─────────┼─────────────────────> author_user_id
  .display_name ────┼─────────────────────> author_display_name
  .avatar ──────────┼─────────────────────> author_avatar
  .author_type ─────┘─────────────────────> author_type

data.text_content ─────────────────────────> text_content
json.dumps(data.media) ───────────────────> media_json        ← serialized in consumer

data.link_preview ──┐                                         ← may be None entirely
  .url ─────────────┼─────────────────────> link_url
  .title ───────────┼─────────────────────> link_title
  .description ─────┼─────────────────────> link_description
  .image ───────────┼─────────────────────> link_image
  .site_name ───────┘─────────────────────> link_site_name

data.stats ─────────┐
  .view_count ──────┼─────────────────────> view_count
  .like_count ──────┼─────────────────────> like_count
  .comment_count ───┼─────────────────────> comment_count
  .share_count ─────┼─────────────────────> share_count
  .save_count ──────┼─────────────────────> save_count
  .engagement_rate ─┼─────────────────────> engagement_rate
  .last_comment_at ─┘─────────────────────> last_comment_at

data.deleted_at ───────────────────────────> deleted_at
data.published_at ─────────────────────────> published_at
data.created_at ───────────────────────────> created_at
data.updated_at ───────────────────────────> updated_at
event.event_id ────────────────────────────> event_id
event.timestamp ───────────────────────────> event_timestamp
```

### The Event Payload (POST_CREATED / all non-delete events)

```json
{
  "event_type": "post.created",
  "event_id": "uuid-string",
  "entity_id": "aaa111bbb222ccc333ddd444",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": {
    "post_type": "text",
    "author": {
      "user_id": "507f1f77bcf86cd799439011",
      "display_name": "Jane Smith",
      "avatar": "https://cdn.example.com/avatars/jane.jpg",
      "author_type": "user"
    },
    "text_content": "Just discovered an amazing new ceramic workshop!",
    "media": [
      {
        "media_type": "image",
        "url": "https://cdn.example.com/posts/workshop.jpg",
        "thumbnail_url": "https://cdn.example.com/posts/workshop_thumb.jpg",
        "alt_text": "Ceramic workshop"
      }
    ],
    "link_preview": {
      "url": "https://example.com/workshop",
      "title": "Amazing Ceramic Workshop",
      "description": "Learn ceramic arts from master craftsmen",
      "image": "https://example.com/og-image.jpg",
      "site_name": "Example.com"
    },
    "stats": {
      "view_count": 0,
      "like_count": 0,
      "comment_count": 0,
      "share_count": 0,
      "save_count": 0,
      "engagement_rate": 0.0,
      "last_comment_at": null
    },
    "deleted_at": null,
    "published_at": null,
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  }
}
```

**POST_DELETED** (minimal payload):
```json
{
  "event_type": "post.deleted",
  "event_id": "uuid-string",
  "entity_id": "aaa111bbb222ccc333ddd444",
  "timestamp": "2025-01-15T11:00:00Z",
  "data": {
    "post_id": "aaa111bbb222ccc333ddd444"
  }
}
```

---

## 5. IMPLEMENTATION EXERCISES

---

### Exercise 5.1: Define the `posts` Table (DDL)

**Concept:** JSON column, DOUBLE type, compound indexes, soft delete column
**Difficulty:** Medium

#### Implement: Add the `posts` table DDL to `TABLE_DEFINITIONS` in `src/db/tables.py`

```sql
CREATE TABLE IF NOT EXISTS posts (
    post_id             VARCHAR(24) PRIMARY KEY,
    post_type           VARCHAR(20) NOT NULL,
    author_user_id      VARCHAR(24) NOT NULL,
    author_display_name VARCHAR(200),
    author_avatar       TEXT,
    author_type         VARCHAR(20),
    text_content        TEXT,
    media_json          JSON,
    link_url            TEXT,
    link_title          VARCHAR(200),
    link_description    VARCHAR(500),
    link_image          TEXT,
    link_site_name      VARCHAR(200),
    view_count          INT DEFAULT 0,
    like_count          INT DEFAULT 0,
    comment_count       INT DEFAULT 0,
    share_count         INT DEFAULT 0,
    save_count          INT DEFAULT 0,
    engagement_rate     DOUBLE DEFAULT 0.0,
    last_comment_at     DATETIME(6),
    deleted_at          DATETIME(6),
    published_at        DATETIME(6),
    created_at          DATETIME(6) NOT NULL,
    updated_at          DATETIME(6) NOT NULL,
    event_id            VARCHAR(36),
    event_timestamp     DATETIME(6),
    INDEX idx_posts_author (author_user_id),
    INDEX idx_posts_type (post_type),
    INDEX idx_posts_published (published_at),
    INDEX idx_posts_created (created_at)
)
```

**Key design decisions:**
- `media_json JSON` — stores the full media list as JSON. MySQL's `JSON` type validates that the stored value is valid JSON and allows JSON functions like `JSON_LENGTH(media_json)` for analytics
- `engagement_rate DOUBLE DEFAULT 0.0` — `DOUBLE` provides 64-bit floating-point precision. `DEFAULT 0.0` ensures new rows start with zero engagement
- `link_url TEXT` and `link_image TEXT` — URLs can be very long, especially with tracking parameters
- `deleted_at DATETIME(6)` — nullable soft delete marker, same pattern as the `users` table
- `published_at DATETIME(6)` — nullable because draft posts are not yet published. The index on this column enables queries like "all published posts sorted by publication date"
- No FK to `users` on `author_user_id` — same reasoning as Product's `supplier_id`: events may arrive out of order

#### Verify Exercise 5.1

```bash
docker compose restart mysql-service

docker compose exec mysql mysql -u analytics -panalytics123 analytics -e "SHOW CREATE TABLE posts\G"
```

---

### Exercise 5.2: Write the DAL Methods (Raw SQL)

**Concept:** 26-parameter upsert with selective update columns + soft delete
**Difficulty:** Medium-High

#### Implement: Two methods in `PostDAL` in `src/dal/post_dal.py`

```python
def upsert_post(self, post_id, post_type,
                author_user_id, author_display_name,
                author_avatar, author_type,
                text_content, media_json,
                link_url, link_title, link_description,
                link_image, link_site_name,
                view_count, like_count, comment_count,
                share_count, save_count, engagement_rate,
                last_comment_at,
                deleted_at, published_at, created_at, updated_at,
                event_id, event_timestamp):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO posts
                (post_id, post_type,
                 author_user_id, author_display_name,
                 author_avatar, author_type,
                 text_content, media_json,
                 link_url, link_title, link_description,
                 link_image, link_site_name,
                 view_count, like_count, comment_count,
                 share_count, save_count, engagement_rate,
                 last_comment_at,
                 deleted_at, published_at, created_at, updated_at,
                 event_id, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                post_type=VALUES(post_type),
                author_display_name=VALUES(author_display_name),
                author_avatar=VALUES(author_avatar),
                text_content=VALUES(text_content),
                media_json=VALUES(media_json),
                link_url=VALUES(link_url), link_title=VALUES(link_title),
                link_description=VALUES(link_description),
                link_image=VALUES(link_image),
                link_site_name=VALUES(link_site_name),
                view_count=VALUES(view_count),
                like_count=VALUES(like_count),
                comment_count=VALUES(comment_count),
                share_count=VALUES(share_count),
                save_count=VALUES(save_count),
                engagement_rate=VALUES(engagement_rate),
                last_comment_at=VALUES(last_comment_at),
                deleted_at=VALUES(deleted_at),
                published_at=VALUES(published_at),
                updated_at=VALUES(updated_at),
                event_id=VALUES(event_id),
                event_timestamp=VALUES(event_timestamp)
        """, (post_id, post_type,
              author_user_id, author_display_name,
              author_avatar, author_type,
              text_content, media_json,
              link_url, link_title, link_description,
              link_image, link_site_name,
              view_count, like_count, comment_count,
              share_count, save_count, engagement_rate,
              last_comment_at,
              deleted_at, published_at, created_at, updated_at,
              event_id, event_timestamp))
        cursor.close()
    finally:
        conn.close()

def soft_delete_post(self, post_id, event_id, event_timestamp):
    conn = get_database().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE posts SET deleted_at = NOW(6),
                event_id = %s, event_timestamp = %s
            WHERE post_id = %s
        """, (event_id, event_timestamp, post_id))
        cursor.close()
    finally:
        conn.close()
```

**Key design decisions:**
- The UPDATE clause skips `post_id` (PK), `author_user_id` (immutable — the author of a post doesn't change), `author_type` (immutable), and `created_at` (immutable)
- `author_display_name` and `author_avatar` **are** updated — the author snapshot in the post event reflects the author's current profile, so we keep it current
- `media_json` arrives as a pre-serialized JSON string from the consumer (the consumer calls `json.dumps()`). The DAL passes it straight through to MySQL's JSON column
- `soft_delete_post` is identical in pattern to `soft_delete_user` — UPDATE with `NOW(6)`, not DELETE

#### Verify Exercise 5.2

```bash
docker compose restart mysql-service
docker compose logs mysql-service | tail -10
```

---

### Exercise 5.3: Write the Consumer Event Handlers

**Concept:** `json.dumps()` for media serialization, optional link_preview flattening, 4 event types
**Difficulty:** Medium

#### Implement: All methods in `PostConsumer` in `src/consumers/post_consumer.py`

> **Don't forget** to add `import json` at the top of `post_consumer.py`.

```python
def _parse_ts(self, ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def _handle_post_upsert(self, event: dict):
    """Shared handler for all events that send full post model."""
    data = event.get("data", {})
    author = data.get("author", {})
    stats = data.get("stats", {})
    link = data.get("link_preview") or {}
    media = data.get("media", [])

    self._dal.upsert_post(
        post_id=event.get("entity_id"),
        post_type=data.get("post_type"),
        author_user_id=author.get("user_id"),
        author_display_name=author.get("display_name"),
        author_avatar=author.get("avatar"),
        author_type=author.get("author_type"),
        text_content=data.get("text_content"),
        media_json=json.dumps(media) if media else None,
        link_url=link.get("url"),
        link_title=link.get("title"),
        link_description=link.get("description"),
        link_image=link.get("image"),
        link_site_name=link.get("site_name"),
        view_count=stats.get("view_count", 0),
        like_count=stats.get("like_count", 0),
        comment_count=stats.get("comment_count", 0),
        share_count=stats.get("share_count", 0),
        save_count=stats.get("save_count", 0),
        engagement_rate=stats.get("engagement_rate", 0.0),
        last_comment_at=self._parse_ts(stats.get("last_comment_at")),
        deleted_at=self._parse_ts(data.get("deleted_at")),
        published_at=self._parse_ts(data.get("published_at")),
        created_at=self._parse_ts(data.get("created_at")),
        updated_at=self._parse_ts(data.get("updated_at")),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )

def handle_post_created(self, event: dict):
    self._handle_post_upsert(event)
    logger.info(f"[POST_CREATED] {event['entity_id']}")

def handle_post_updated(self, event: dict):
    self._handle_post_upsert(event)
    logger.info(f"[POST_UPDATED] {event['entity_id']}")

def handle_post_published(self, event: dict):
    self._handle_post_upsert(event)
    logger.info(f"[POST_PUBLISHED] {event['entity_id']}")

def handle_post_deleted(self, event: dict):
    data = event.get("data", {})
    self._dal.soft_delete_post(
        post_id=data.get("post_id") or event.get("entity_id"),
        event_id=event.get("event_id"),
        event_timestamp=self._parse_ts(event.get("timestamp")),
    )
    logger.info(f"[POST_DELETED] {event['entity_id']}")

def get_handlers(self) -> dict:
    return {
        EventType.POST_CREATED: self.handle_post_created,
        EventType.POST_UPDATED: self.handle_post_updated,
        EventType.POST_PUBLISHED: self.handle_post_published,
        EventType.POST_DELETED: self.handle_post_deleted,
    }
```

**Key design decisions:**
- `link = data.get("link_preview") or {}` — uses `or {}` instead of a default in `.get()`. This is because `link_preview` may be explicitly `None` in the event payload (not just missing). `data.get("link_preview", {})` would return `None` when the key exists with value `None`, but `or {}` converts `None` to `{}`
- `json.dumps(media) if media else None` — the consumer serializes the media list to a JSON string **before** passing it to the DAL. If the media list is empty, pass `None` instead (no point storing `"[]"` in the JSON column)
- `stats.get("engagement_rate", 0.0)` — defaults to `0.0` (float), matching the `DOUBLE DEFAULT 0.0` column
- `last_comment_at` comes from `stats` (not from `data` directly) — it's nested inside the stats object
- The delete handler uses **soft delete** (like User), not hard delete (like Product/Supplier)

#### Verify Exercise 5.3

**Step 1: Restart**
```bash
docker compose restart mysql-service
```

**Step 2: Create a post** (requires a user to exist)
```bash
# Create a user first (if you don't have one)
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email": "post-author@example.com", "password": "Pass123!", "display_name": "Post Author"}'
# Save the user ID

# Create a post
curl -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -H "X-User-ID: <user-id>" \
  -d '{
    "post_type": "text",
    "text_content": "Testing the analytics pipeline!"
  }'
```

Save the returned post `id`.

**Step 3: Check consumer logs**
```bash
docker compose logs mysql-service | grep POST_CREATED
```

**Step 4: Query MySQL**
```bash
docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT post_id, post_type, author_display_name, text_content, engagement_rate, media_json, published_at FROM posts\G"
```

**Expected:** Row with `post_type=text`, `author_display_name=Post Author`, `engagement_rate=0`, `published_at=NULL` (draft).

**Step 5: Publish and verify**
```bash
curl -X POST http://localhost:8000/posts/<post-id>/publish \
  -H "X-User-ID: <user-id>"

docker compose logs mysql-service | grep POST_PUBLISHED

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT post_id, published_at FROM posts WHERE post_id = '<post-id>'\G"
# published_at should now have a timestamp
```

**Step 6: Test soft delete**
```bash
curl -X DELETE http://localhost:8000/posts/<post-id> \
  -H "X-User-ID: <user-id>"

docker compose logs mysql-service | grep POST_DELETED

docker compose exec mysql mysql -u analytics -panalytics123 analytics \
  -e "SELECT post_id, deleted_at FROM posts WHERE post_id = '<post-id>'\G"
# deleted_at should have a timestamp, row still exists
```

---

## 6. VERIFICATION CHECKLIST

### Table Checks
- [ ] `SHOW TABLES;` includes `posts`
- [ ] `DESCRIBE posts;` shows 26 columns
- [ ] `media_json` column type is `json`
- [ ] `engagement_rate` column type is `double` with default `0`
- [ ] 4 indexes: `idx_posts_author`, `idx_posts_type`, `idx_posts_published`, `idx_posts_created`

### Functional Checks
- [ ] **Create post** -> `[POST_CREATED]` in logs -> row in MySQL with correct author snapshot
- [ ] **`published_at` is NULL** for a draft post
- [ ] **Publish post** -> `[POST_PUBLISHED]` in logs -> `published_at` now has a timestamp
- [ ] **`media_json`** is either `NULL` (no media) or valid JSON (e.g., `[{"media_type": "image", ...}]`)
- [ ] **Link preview columns** are NULL when no link preview is present
- [ ] **Engagement stats** all start at 0, `engagement_rate` at 0.0
- [ ] **Delete post** -> `[POST_DELETED]` in logs -> `deleted_at` set, row still exists (soft delete)

### Code Quality Checks
- [ ] `import json` present in `post_consumer.py`
- [ ] `json.dumps(media) if media else None` — not `json.dumps([])` for empty media
- [ ] `data.get("link_preview") or {}` — handles explicit `None` value correctly
- [ ] `last_comment_at` extracted from `stats` (not `data`)
- [ ] `get_handlers()` maps all 4 EventTypes
- [ ] `try/finally` on every DAL method

---

## 7. ADVANCED CHALLENGES

### Challenge A: JSON Functions in MySQL

MySQL supports querying inside JSON columns. Try these on your posts data:

```sql
-- Count media items per post
SELECT post_id, JSON_LENGTH(media_json) as media_count
FROM posts
WHERE media_json IS NOT NULL;

-- Extract the first media item's type
SELECT post_id, JSON_EXTRACT(media_json, '$[0].media_type') as first_media_type
FROM posts
WHERE media_json IS NOT NULL;

-- Find posts with images
SELECT post_id, text_content
FROM posts
WHERE JSON_CONTAINS(media_json, '"image"', '$[*].media_type');
```

**Takeaway:** JSON columns let you store semi-structured data while still allowing SQL-level queries. The trade-off vs a child table: JSON queries are slower and can't use traditional indexes, but the schema is simpler.

### Challenge B: JSON Column vs Child Table

Compare the Post approach (JSON column for media) with the Product approach (child table for variants):

| Aspect | `media_json` (JSON column) | `product_variants` (child table) |
|--------|---------------------------|----------------------------------|
| Query individual items | Possible but slow (JSON functions) | Fast (standard SQL, indexes) |
| Count items | `JSON_LENGTH()` | `COUNT(*)` with GROUP BY |
| Filter by item field | `JSON_CONTAINS()` (no index) | `WHERE` clause (indexable) |
| Schema flexibility | Fully flexible | Fixed columns |
| When to use | Display-only, small lists | Queryable, joinable, large sets |

**Question:** Why was JSON chosen for media but a child table for variants?

**Answer:** Variants are a core analytics dimension — you need to query "which variant sells the most", "average price per variant", etc. Media attachments are display metadata — you rarely query "find all posts with exactly 3 images of type video". The query requirements drive the schema decision.

---

## 8. WHAT'S NEXT

You've handled all the single-table and single-parent/child domains. You now understand:
- JSON columns for semi-structured lists
- DOUBLE type for floating-point metrics
- Optional object flattening (link_preview -> 4 columns)
- `json.dumps()` serialization in the consumer layer
- Compound indexes for different query patterns
- Soft delete (User, Post) vs hard delete (Supplier, Product)

**TASK 07: Order** is the capstone — the most complex domain:
- **Two tables** again — `orders` (parent) + `order_items` (child)
- **UNIQUE KEY on a business field** — `order_number` (not just the PK)
- **Selective ON DUPLICATE KEY UPDATE** — only update `status` and timestamps on the order, not immutable customer/shipping data
- **Batch INSERT in a loop** for order items with `product_snapshot` flattening
- **Composite UNIQUE** on child table `(order_id, item_id)`
- **Cancel by business key** — UPDATE WHERE `order_number` (not PK)
- Only 2 event types, but the most complex handler logic
