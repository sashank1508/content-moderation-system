# AI-Powered Content Moderation System

# **🚀 Overview**

This project implements a **scalable, high-performance** content moderation system using **FastAPI, Celery, Redis, PostgreSQL, and OpenAI's moderation API**. The system **processes text & image content**, implements **caching, asynchronous task processing**, and provides **monitoring with Prometheus**.

It follows a **microservices architecture** with **Docker & Docker Compose** for deployment.

---

# **📜 Features**

✔ **FastAPI-based API for text & image moderation**  
✔ **Asynchronous task processing with Celery**  
✔ **Caching & message queuing with Redis**  
✔ **Database persistence in PostgreSQL**  
✔ **Database migrations with Alembic** to track schema changes and updates  
✔ **Dead Letter Queue (DLQ)** to store & retry failed moderation tasks  
✔ **Mock API** to simulate OpenAI’s moderation for testing & failover support  
✔ **Rate limiting** to prevent API abuse and ensure fair usage  
✔ **Efficient indexing** for high-performance database queries  
✔ **Structured logging & monitoring** using Prometheus & Structlog  
✔ **Health checks for API, DB, Redis, Celery** to ensure system stability  
✔ **Robust error handling & retry mechanisms** for better fault tolerance  
✔ **Docker-based deployment** for easy setup & scaling  
✔ **Load testing with Locust** to benchmark system performance  
✔ **Unit testing with Pytest** ensuring reliable and bug-free code

---

## **🛠️ Tech Stack**

| Technology                         | Purpose                                                                      |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| **FastAPI**                        | High-performance API framework for handling requests & responses efficiently |
| **Celery**                         | Background task processing for asynchronous moderation tasks                 |
| **Redis**                          | Caching, rate limiting, and message queuing for fast task processing         |
| **PostgreSQL**                     | Database for storing moderation results with efficient indexing strategies   |
| **Alembic**                        | Database migrations and schema management for version control                |
| **OpenAI API**                     | AI-powered text and image moderation service                                 |
| **Mock API**                       | Simulated moderation API for testing and failover support                    |
| **Pydantic**                       | Data validation and serialization for API request handling                   |
| **Docker**                         | Containerized deployment for easy setup and scaling                          |
| **Docker Compose**                 | Service orchestration for managing multiple containers efficiently           |
| **Prometheus**                     | System monitoring and metric collection for observability                    |
| **Structlog**                      | Structured logging for better debugging and tracing                          |
| **pytest**                         | Unit testing framework ensuring robust and bug-free code                     |
| **pytest-asyncio**                 | Asynchronous testing support for FastAPI and Celery components               |
| **pytest-cov**                     | Code coverage analysis for test completeness                                 |
| **Locust**                         | Load testing tool to benchmark system performance under high traffic         |
| **Uvicorn**                        | ASGI server for serving FastAPI with high concurrency                        |
| **httpx**                          | Async HTTP client for handling external API requests                         |
| **SQLAlchemy**                     | ORM for database interactions and query optimization                         |
| **asyncpg**                        | Asynchronous PostgreSQL driver for efficient DB queries                      |
| **Celery Beat**                    | Periodic task scheduler for automated background jobs                        |
| **Dead Letter Queue (DLQ)**        | Stores failed tasks and retries them automatically                           |
| **Rate Limiter (fastapi-limiter)** | Protects APIs from abuse by enforcing request limits                         |
| **dotenv**                         | Manages environment variables securely                                       |
| **mypy**                           | Static type checker for Python to catch type-related errors early            |

---

# **📦 System Architecture**

The system follows a **scalable microservices architecture** with **separate nodes** for handling:

1. **New Moderation Requests**
2. **Retrieving Moderation Results (from Redis or PostgreSQL)**
3. **Asynchronous Processing via Celery Workers**

---

### **🔹 System Workflow**

1️⃣ **Client sends text/image for moderation** → **FastAPI Node (API Gateway)**

2️⃣ **FastAPI Node** validates request and **queues the task in Redis**

3️⃣ **Celery Worker picks up task**, calls **OpenAI API (or Mock API), processes it**, and stores results in:

- **Redis (Cache)**
- **PostgreSQL (Permanent Storage)**

4️⃣ **Client requests moderation result using ID** → **FastAPI (Result Retrieval Node)**

5️⃣ **Result Retrieval Node checks Redis**:

- **If found:** Returns result from cache
- **If expired:** Queries PostgreSQL

6️⃣ **Client receives response**

---

### **🛠️ Detailed Architecture**

```plaintext
                 ┌───────────────────────────────┐
                 │        Client (User)          │
                 │ (Sends text/image for review) │
                 └──────────────┬────────────────┘
                                │
                                ▼
                 ┌──────────────────────────┐
                 │   FastAPI (API Gateway)  │
                 │   - Validates Requests   │
                 │   - Rate Limiting        │
                 │   - Sends Task to Queue  │
                 └──────┬───────────────────┘
                        │
      ┌────────────────┴───────────────┐
      │                                │
      ▼                                ▼
┌──────────────┐               ┌──────────────────┐
│   PostgreSQL │               │    Redis         │
│ (Database)   │               │  (Cache & MQ)    │
│ Stores       │               │ - Caches Results │
│ Moderation   │               │ - Manages Queue  │
│ Results      │               │ - Rate Limiting  │
└──────────────┘               └──────────────────┘
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │       Celery Worker      │
                          │  - Calls OpenAI API      │
                          │  - Stores Results in DB  │
                          │  - Uses Redis as Queue   │
                          └─────────────┬────────────┘
                                        │
               ┌────────────────────┐   ▼
               │ Celery Beat        │
               │ (Task Scheduler)   │─────────> Dead Letter Queue (DLQ)
               │ - Retries Failed   │
               │   Moderation Jobs  │
               └────────────────────┘

           ┌───────────────────────────┐
           │ FastAPI (Result Retrieval)│
           │ - Checks Redis for Result │
           │ - If expired, Queries DB  │
           │ - Returns Moderation Data │
           └───────────────────────────┘

                ┌────────────────────────┐
                │     Prometheus         │
                │  (Monitoring & Logs)   │
                │ - Tracks API Traffic   │
                │ - Monitors Workers     │
                └────────────────────────┘
```

---

# **📥 Setup Instructions**

You can set up the project **with or without Docker**.

---

### **🛠️ Setup Without Docker (Local Machine)**

1️⃣ **Clone the repository:**

```sh
git clone https://github.com/sashank1508/content-moderation-system
cd content-moderation-system
```

2️⃣ **Create a virtual environment:**

```sh
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

3️⃣ **Install dependencies:**

```sh
pip install -r requirements.txt
```

4️⃣ **Set up PostgreSQL database:**

```sh
sudo -i -u postgres
createuser --interactive --pwprompt
createdb stepsdb --owner=stepsuser
sudo systemctl start postgresql
```

5️⃣ **Set up Redis:**

```sh
sudo apt install redis
sudo systemctl start redis
# Check
sudo systemctl status redis
redis-cli ping
```

6️⃣ **Run database migrations:**

```sh
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

7️⃣ **Start FastAPI server:**

```sh
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

or

```sh
python3 main.py
```

8️⃣ **Start Mock server:**

```sh
uvicorn mock:mock_app --host 127.0.0.1 --port 8080 --reload
```

or

```sh
python3 mock.py
```

9️⃣ **Start Celery worker:**

```sh
celery -A celery_worker worker --pool=gevent --loglevel=info --concurrency=4
```

🔟 **Start Celery beat scheduler:**

```sh
celery -A celery_worker beat --loglevel=info
```

**Run tests to verify everything works:**

```sh
pytest
```

### **🐳 Setup With Docker (Recommended)**

1️⃣ **Clone the repository:**

```sh
git clone https://github.com/sashank1508/content-moderation-system
cd content-moderation-system
```

2️⃣ **Build Docker images:**

```sh
docker-compose build
```

Run this command whenever you update dependencies or modify Dockerfiles.

3️⃣ **Start Containers:**

```sh
docker-compose up # To Run in Detached Mode: docker-compose up -d
```

This runs the containers in foreground mode, displaying logs in real-time. Use detached mode (-d) when you want the services to run in the background and free up the terminal.

The system is now running on http://localhost:8000/

**To stop containers:**

```sh
docker-compose down
```

**For newer Docker versions:**

```sh
docker compose build
docker compose up  # Run in detached mode: docker compose up -d
docker compose down
```

---

# **📌 API Documentation**

This API provides **AI-powered content moderation** for **text and images** using **FastAPI, Celery, Redis, and PostgreSQL**.

📌 **Base URL:** `http://localhost:8000/` (Swagger UI)

---

## **Content Moderation Endpoints**

### POST `/api/v1/moderate/text`

Asynchronously processes text moderation using Celery.

**Request Body:**

```json
{
  "text": "string" // Text content to be moderated
}
```

**Response:**

```json
{
  "message": "Text Moderation Task Queued",
  "text": "string",
  "id": "uuid"
}
```

### POST `/api/v1/moderate/image`

Asynchronously processes image moderation using Celery.

**Request Body:**

```json
{
  "image_url": "string" // URL of the image to be moderated
}
```

**Response:**

```json
{
  "message": "Image Moderation Task Queued",
  "image_url": "string",
  "id": "uuid"
}
```

## Moderation Results Management

### GET `/api/v1/moderation/{id}`

Retrieves moderation result for a specific ID.

**Parameters:**

- `id` (path): Unique identifier of the moderation task

**Response:**

```json
{
  "message": "string",
  "id": "string",
  "text": "string",
  "status": "string",
  "result": "object",
  "created_at": "datetime"
}
```

### GET `/api/v1/moderation/all`

Retrieves all moderation tasks with pagination.

**Query Parameters:**

- `offset` (integer, default: 0): Starting index for pagination
- `limit` (integer, default: 10, range: 1-100): Maximum number of records to retrieve

**Response:**

```json
{
  "total_count": "integer",
  "offset": "integer",
  "limit": "integer",
  "tasks": [
    {
      "id": "string",
      "text": "string",
      "status": "string",
      "result": "object",
      "created_at": "datetime"
    }
  ]
}
```

### DELETE `/api/v1/moderation/clear_all`

Deletes all moderation results from the database.

**Response:**

```json
{
  "status": "string",
  "message": "string"
}
```

### DELETE `/api/v1/moderation/clear/{id}`

Deletes a specific moderation result by ID.

**Parameters:**

- `id` (path): Unique identifier of the moderation task

**Response:**

```json
{
  "status": "string",
  "message": "string"
}
```

## Failed Tasks Management

### GET `/api/v1/moderation/failed`

Retrieves all failed moderation tasks from the Dead Letter Queue (DLQ).

**Response:**

```json
{
  "status": "string",
  "message": "string",
  "failed_tasks": ["array"]
}
```

### DELETE `/api/v1/moderation/failed/clear`

Clears all failed moderation tasks from the DLQ.

**Response:**

```json
{
  "status": "string",
  "message": "string"
}
```

### DELETE `/api/v1/moderation/failed/{id}/clear`

Removes a specific failed task from the DLQ.

**Parameters:**

- `id` (path): Unique identifier of the failed task

**Response:**

```json
{
  "status": "string",
  "message": "string"
}
```

## Monitoring and Debug Endpoints

### GET `/api/v1/health`

Checks the health status of all system components.

**Response:**

```json
{
  "api": "string",
  "status": "string",
  "database": "object",
  "redis": "object",
  "celery": "object"
}
```

### GET `/api/v1/debug/db`

Checks database connection and returns record count.

**Response:**

```json
{
  "database_status": "string",
  "row_count": "integer"
}
```

### GET `/stats`

Returns Prometheus metrics in plain text format.

### GET `/metrics/json`

Returns Prometheus metrics in JSON format.

**Response:**

```json
{
  "metric_name": {
    "type": "string",
    "help": "string",
    "values": [
      {
        "labels": "object",
        "value": "number"
      }
    ]
  }
}
```

## Rate Limiting

All endpoints are protected by rate limiting:

- 10 requests per 60 seconds per client

## Error Responses

All endpoints may return the following error responses:

- `400 Bad Request`: Invalid input parameters
- `404 Not Found`: Requested resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server-side error

## Request/Response Models

### TextModerationRequest

- `text` (string, required): Text content to be analyzed for moderation with a minimum length of 1 character.

### ImageModerationRequest

- `image_url` (string, required): A valid HTTP/HTTPS URL pointing to the image that needs to be moderated.

### ModerationResultResponse

- Contains moderation outcome with `message`, `id`, `text`, `status`, `result` (as JSON), and `created_at` timestamp.

---

# **📊 Performance Considerations**

### ✔ Scalability

- **FastAPI + Celery + Redis** ensures **non-blocking, high-throughput processing**
- **Asynchronous database queries** improve performance

### ✔ Caching

- **Redis caches results** for **faster API responses**
- Moderation results **expire after 1 hour** to prevent stale data

### ✔ Error Recovery

- **Dead Letter Queue (DLQ)** stores **failed tasks** for retry
- **Exponential backoff retries** prevent **task failures from overwhelming the system**

### ✔ Monitoring

- **Prometheus** collects metrics (`/metrics/json`, `/stats`)
- **Structured logs** make debugging easier

### ✔ Health Checks

- **API**: Verifies API service is running
- **Database**: Checks PostgreSQL connectivity and queries
- **Redis**: Validates Redis connection and operations
- **Celery**: Confirms worker processes are active
- **Endpoint**: `/api/v1/health` returns status of all components

---

# 🔧 Environment Configuration (`.env` File)

The `.env` file contains environment variables for configuring **Redis, PostgreSQL, OpenAI API, and the Mock Server**.  
Use different values depending on whether you are **running locally** or **inside Docker**.

## 📌 Without Docker (Local Setup)
Use these values if you are running everything **directly on your machine** (without Docker):

```ini
# Redis running on local machine
REDIS_URL=redis://localhost:6379/0

# PostgreSQL running on local machine
DATABASE_URL=postgresql+asyncpg://stepsuser:stepsai@localhost:5432/stepsdb

# OpenAI API Key (Replace with your actual key)
OPENAI_API_KEY=sk-your-api-key-here

# Use Mock API (false = Use OpenAI API, true = Use local Mock API)
USE_MOCK_SERVER=false
```

## 🐳 With Docker
Use these values if you are running **Redis and PostgreSQL inside Docker containers**:

```ini
# Redis inside Docker (connects to the redis service)
REDIS_URL=redis://redis:6379/0

# PostgreSQL inside Docker (connects to the db service)
DATABASE_URL=postgresql+asyncpg://stepsuser:stepsai@db:5432/stepsdb

# OpenAI API Key (Replace with your actual key)
OPENAI_API_KEY=sk-your-api-key-here

# Use Mock API (false = Use OpenAI API, true = Use local Mock API)
USE_MOCK_SERVER=false
```

## ⚠️ Important:
* If you are using **Docker**, your FastAPI app should refer to services by their **Docker Compose service names** (`redis`, `db`).
* If you are **not using Docker**, you should use `localhost` instead.

## 🧠 Configuring `USE_MOCK_SERVER`
`USE_MOCK_SERVER` determines whether the system should **use OpenAI's moderation API** or **a local mock API**.

| Value | Behavior |
|-------|----------|
| `false` | Uses OpenAI's **real** moderation API (**Recommended for production**) |
| `true` | Uses a **mock API** instead of OpenAI (**Use for testing & development**) |
---

# **📝 Testing**

## **Unit Tests (With Pytest)**

Unit tests ensure the system works as expected.

### Run All Tests

```sh
pytest
```

### Run Specific Test Files

```sh
pytest tests/test_main.py
pytest tests/test_database.py
pytest tests/test_tasks.py
```

### Run Tests with Coverage Report

```sh
pytest --cov=.
```

This generates a test coverage report to check how much of the code is tested.

## **Load Testing with Locust**

You can simulate high traffic to test system performance.

### Install Locust

```sh
pip install locust
```

### Run Load Test

```sh
locust -f locustfile.py --host=http://localhost:8000
```

Now, open your browser and go to ➡ http://localhost:8089/ to start the test.

---

# 📌 Conclusion

This project efficiently moderates **text & images** using **AI**, queues tasks asynchronously with **Celery**, caches results in **Redis**, and persists data in **PostgreSQL**.

It follows a **microservices architecture**, ensuring **scalability, fault tolerance, and production readiness**.  
With **structured logging, monitoring, and automated testing**, the system is **robust and reliable** for real-world deployment.
