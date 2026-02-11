# TASK: Docker Compose - Service Configuration

## Overview

The `docker-compose.yml` file defines 5 services that make up the Social Commerce Platform. The skeleton is in place (images, ports, networks, healthchecks, build contexts, dependencies) but each service is missing its **environment variables** and **volumes**. You need to configure both.

```
docker-compose.yml
├── mongodb          ← Database: MongoDB (operational data)
├── kafka            ← Message broker: Kafka in KRaft mode
├── app              ← Backend: FastAPI + Beanie (produces events)
├── mysql            ← Database: MySQL (analytics data)
└── mysql-service    ← Consumer: Kafka → MySQL (consumes events)
```

### Two Types of Volumes You'll Configure

**Named volumes** persist data across container restarts. Without them, databases lose all data when a container is recreated. Named volumes are managed by Docker and declared in a top-level `volumes:` section at the bottom of the compose file.

```yaml
# Service-level: mount a named volume
volumes:
  - volume_name:/path/inside/container

# Top-level: declare the named volume
volumes:
  volume_name:
    driver: local
```

**Bind mounts** map a directory on your host machine into a container. They enable live code reloading - when you edit files on your machine, the changes are immediately visible inside the container.

```yaml
volumes:
  - ./local/path:/container/path
```

---

## Service 1: MongoDB (`mongodb`)

**Image:** `mongo:latest` | **Port:** `27017`

MongoDB is the primary data store. The official `mongo` image supports an environment variable that tells the container which database to create on first startup.

**Environment:**
- The initial database name that MongoDB creates when the container starts for the first time

**Volumes:**
- A named volume to persist MongoDB data. The `mongo` image stores its data files at `/data/db` inside the container. Without this volume, all documents are lost on container restart.

**Where the app reads it:** `apps/mongo_backend/db/mongo_db.py` reads `DATABASE_NAME` to know which database to connect to. The database name in the compose file should match.

---

## Service 2: Kafka (`kafka`)

**Image:** `confluentinc/cp-kafka:7.6.0` | **Port:** `9092`

Kafka runs in **KRaft mode** (no Zookeeper). This is a single-node cluster where the same node acts as both broker and controller. The Confluent `cp-kafka` image reads configuration from environment variables.

**Environment:**

You need to set environment variables covering these areas:

**Node identity**
- Every Kafka node needs a unique numeric ID
- In KRaft mode, each node declares its roles (this node is both broker and controller)

**Controller quorum**
- The controller quorum voters list tells each node who participates in leader election
- Format: `nodeId@hostname:controllerPort`
- The controller uses its own dedicated listener (separate from client connections)

**Listeners and networking**
- Kafka needs two listeners: one for client traffic (PLAINTEXT protocol, port `9092`) and one for controller communication (port `29093`)
- Advertised listeners tell other Docker services how to reach this broker (use the Docker service name as hostname)
- A security protocol map assigns a protocol to each listener name
- Specify which listener handles inter-broker communication

**Cluster settings**
- A cluster ID (any Base64 string) identifies this Kafka cluster
- The offsets topic replication factor must be set to `1` for a single-node cluster
- Enable auto-creation of topics so producers don't need to pre-create them
- Set the log directory to match the volume mount path

**Volumes:**
- A named volume to persist Kafka log segments and topic data. Kafka stores its data at `/var/lib/kafka/data` inside the container. The Kafka log directory environment variable should point to this same path.

---

## Service 3: App (`app`)

**Build:** `./apps/mongo_backend` | **Port:** `8000`

The FastAPI backend connects to MongoDB for data storage and to Kafka for producing events.

**Environment:**

- **MongoDB connection:** The app needs to know the MongoDB URL and database name
  - Look at `apps/mongo_backend/db/mongo_db.py` to see which environment variables are read and what the connection URL format should be (the hostname is the Docker service name `mongodb`)

- **Kafka producer:** The app needs to connect to Kafka as a producer
  - Look at `shared/kafka/config.py` (`KafkaConfig.from_env()`) to see which environment variables are read
  - The Kafka hostname is the Docker service name `kafka`

**Volumes:**
- Two bind mounts for live code reloading:
  - The app source code directory (`./apps/mongo_backend`) mounted to `/app` inside the container
  - The shared library directory (`./shared`) mounted to `/app/shared` inside the container
- This means you can edit Python files on your host machine and the changes take effect immediately (with auto-reload)

---

## Service 4: MySQL (`mysql`)

**Image:** `mysql:8.0` | **Port:** `3306`

MySQL stores the analytics replica data. The official `mysql` image supports environment variables for initial setup.

**Environment:**

The MySQL image requires these on first startup:
- A root password
- The name of the database to create
- A non-root user to create
- The password for that non-root user

**Volumes:**
- A named volume to persist MySQL table data, indexes, and logs. The `mysql` image stores its data at `/var/lib/mysql` inside the container.

**Where it's referenced:** The `mysql-service` container and the `connection.py` pool both connect using these same credentials. Whatever user/password/database you set here must match what the mysql-service uses.

---

## Service 5: MySQL Service (`mysql-service`)

**Build:** `./apps/mysql_server`

The Kafka consumer service that reads events and writes to MySQL. It needs connection details for both Kafka (to consume events) and MySQL (to write data).

**Environment:**

- **Kafka consumer:** The service needs Kafka broker address, a client ID, and a consumer group ID
  - Look at `shared/kafka/config.py` (`KafkaConfig.from_env()` and `to_consumer_config()`) to see which environment variables are read
  - Look at `apps/mysql_server/main.py` to see what group ID parameter is passed

- **MySQL connection:** The service needs host, port, user, password, and database
  - Look at `apps/mysql_server/src/db/connection.py` to see which environment variables are read (in the answer for TASK_00)
  - The hostname is the Docker service name `mysql`
  - Credentials must match what you configured in the `mysql` service above

**Volumes:**
- Two bind mounts for live code reloading (same pattern as the `app` service):
  - The mysql_server source code directory mounted to `/app`
  - The shared library directory mounted to `/app/shared`

---

## Top-Level Volumes Declaration

At the bottom of your `docker-compose.yml`, you need a top-level `volumes:` section that declares every named volume used by the services above. Each named volume uses the `local` driver.

You should have 3 named volumes total (one per database/stateful service). The two application services (`app` and `mysql-service`) use bind mounts, which don't need top-level declarations.

---

## Verification

After configuring all services:

```bash
# Start all services
docker compose up -d

# Verify all 5 containers are running
docker compose ps

# Test MongoDB
docker compose exec mongodb mongosh --eval "db.runCommand('ping')"

# Test Kafka
docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Test MySQL
docker compose exec mysql mysqladmin ping -h localhost

# Test App
curl http://localhost:8000/docs

# Check mysql-service logs
docker compose logs mysql-service
```

All 5 services should show as running. If a service fails to start, check its logs with `docker compose logs <service-name>`.

### Verify Data Persistence

```bash
# Restart containers and confirm data survives
docker compose down
docker compose up -d

# MongoDB data should still be there
docker compose exec mongodb mongosh --eval "db.getCollectionNames()"

# MySQL tables should still exist
docker compose exec mysql mysqladmin ping -h localhost
```

If data is lost after restart, your named volumes are not configured correctly.
