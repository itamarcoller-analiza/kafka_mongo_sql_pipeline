# Running the Platform & Seed Scripts

## Prerequisites

| Requirement | Version | Check |
|------------|---------|-------|
| Docker Desktop | 4.x+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |
| Python | 3.11+ | `python3 --version` |
| Git | Any | `git --version` |

---

## 1. Start the Platform

```bash
# From the project root (kafka_mongo_sql_pipeline/)
docker compose up -d
```

This starts 5 containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `social_commerce_mongodb` | 27017 | MongoDB (primary data store) |
| `social_commerce_kafka` | 9092 | Kafka broker (event streaming) |
| `social_commerce_app` | 8000 | FastAPI backend |
| `social_commerce_mysql` | 3306 | MySQL (analytics database) |
| `social_commerce_mysql_service` | - | Kafka consumer (writes to MySQL) |

### Verify containers are running

```bash
docker compose ps
```

All containers should show `running` or `Up`.

### Verify the API

Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser. You should see the Swagger UI with all endpoint groups.

---

## 2. Install Python Dependencies (for scripts)

The seed scripts run **outside** Docker and call the API over HTTP. They need `requests` installed locally:

```bash
pip install requests motor beanie pydantic pydantic[email]
```

> `requests` is needed for `seed.py` and `generate_products.py`. `motor`, `beanie`, and `pydantic` are needed for `generate_posts.py` (which writes directly to MongoDB).

---

## 3. Seed Scripts

All scripts are in the `scripts/` directory and must be run from the **project root**.

### Script 1: `seed.py` — Create Users & Suppliers

Creates 1 user and 30 suppliers via the REST API.

```bash
python scripts/seed.py
```

**What it does:**
- Creates a test user: `john@example.com` / `password123`
- Creates 30 suppliers with Israeli business data (company info, contact info, banking info)
- Skips any that already exist (safe to run multiple times)

**Requires:** The `app` container running on `localhost:8000`

**Expected output:**
```
User created: 6789... (john@example.com)
Supplier [1/30] created: 6789... (Cedar Supply Solutions Ltd.)
Supplier [2/30] created: 6789... (Negev Trading Group Ltd.)
...
Done. 30 new suppliers created.
```

---

### Script 2: `generate_products.py` — Create Products

Creates 50 products with variants via the REST API. Requires suppliers to exist first.

```bash
python scripts/generate_products.py
```

**What it does:**
- Fetches all existing suppliers from the API
- Creates 50 products across 5 categories: electronics, clothing, home & garden, food & beverage, sports & outdoors
- Each product has 1-3 variants with realistic pricing
- Assigns products to random suppliers

**Requires:**
- The `app` container running on `localhost:8000`
- At least one supplier (run `seed.py` first)

---

### Script 3: `generate_posts.py` — Create Posts

Creates 100 posts with realistic engagement data. Writes **directly to MongoDB** (not via the API).

```bash
python scripts/generate_posts.py
```

**What it does:**
- Connects directly to MongoDB at `localhost:27017`
- Creates 100 posts with varied types (text, media, link, product review)
- Sets realistic engagement stats (likes, comments, shares, views)
- Sets varied timestamps and publication states
- Creates posts from existing users

**Requires:**
- The `mongodb` container running on `localhost:27017`
- At least one user (run `seed.py` first)

**Environment variables (optional):**
```bash
MONGODB_URL=mongodb://localhost:27017  # default
DATABASE_NAME=social_commerce          # default
```

---

## 4. Recommended Execution Order

Run scripts in this order after `docker compose up -d`:

```bash
# Step 1: Seed users and suppliers
python scripts/seed.py

# Step 2: Generate products (needs suppliers)
python scripts/generate_products.py

# Step 3: Generate posts (needs users, writes directly to MongoDB)
python scripts/generate_posts.py
```

---

## 5. Useful Docker Commands

### View logs

```bash
# FastAPI app logs (your service code)
docker compose logs -f app

# All services
docker compose logs -f

# Kafka consumer (MySQL analytics service)
docker compose logs -f mysql-service

# Specific service since last 5 minutes
docker compose logs --since 5m app
```

### Restart services

```bash
# Restart just the app (after code changes that didn't auto-reload)
docker compose restart app

# Restart everything
docker compose restart
```

### Stop the platform

```bash
# Stop all containers (preserves data)
docker compose down

# Stop and delete all data (fresh start)
docker compose down -v
```

### Rebuild after Dockerfile changes

```bash
docker compose build
docker compose up -d
```

### Access containers directly

```bash
# MongoDB shell
docker compose exec mongodb mongosh social_commerce

# MySQL shell
docker compose exec mysql mysql -u analytics -panalytics123 analytics

# Kafka: list topics
docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Kafka: describe consumer group lag
docker compose exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 \
    --group mysql-analytics-service --describe
```

---

## 6. Troubleshooting

### Port already in use

```bash
# Find what's using the port
lsof -i :8000
# Kill it
kill -9 <PID>
```

### API returns 500 errors

```bash
# Check the full traceback
docker compose logs -f app
```

### Seed script: "Connection refused"

The API container isn't ready yet. Wait a few seconds after `docker compose up -d` and retry.

```bash
# Check if the app is up
curl http://localhost:8000/
# Should return: {"status":"ok",...}
```

### MongoDB: "Connection refused" (for generate_posts.py)

```bash
# Check if MongoDB is accessible locally
docker compose exec mongodb mongosh --eval "db.runCommand('ping')"
```

### Fresh start (nuclear reset)

```bash
docker compose down -v   # Removes all containers + data volumes
docker compose build     # Rebuild images
docker compose up -d     # Start fresh
```
