# 📜 Bulk Certificate Generator

A production-ready backend API that accepts bulk certificate generation requests for large groups of recipients and generates personalized PDF certificates in the background.

---

## 🏗️ Architecture & Design Decisions

### Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Framework** | FastAPI | Async-first, auto-generated OpenAPI docs, Pydantic validation |
| **Database** | PostgreSQL + SQLAlchemy (async) | Relational integrity, UUID primary keys, async sessions for FastAPI |
| **Background Tasks** | Celery + Redis | Decoupled processing, task retry, concurrency control |
| **Task Monitoring** | Flower | Real-time Celery task dashboard |
| **Certificate Generation** | ReportLab | Pure-Python PDF generation, no system deps like wkhtmltopdf |
| **Migrations** | Alembic | Schema version control |
| **Testing** | pytest + pytest-asyncio + SQLite (in-memory) | Fast, hermetic, no external DB needed for tests |
| **Containerization** | Docker + Docker Compose | One-command startup for all services |

### Why Background Processing (Celery)?

> **Decision**: Certificate generation is processed **asynchronously** via Celery workers rather than synchronously in the HTTP request.

**Rationale**:
1. A job can contain thousands of recipients — synchronous processing would time out HTTP connections.
2. Celery workers can be scaled independently of the API server.
3. Individual certificate failures are isolated — one bad recipient does not kill the job.
4. Flower provides real-time visibility into task queue health.
5. Celery supports retries for transient failures (network, disk I/O).

**Trade-off**: The client must poll `GET /jobs/{id}` to check progress, rather than getting an immediate result. This is the correct pattern for long-running batch operations.

### Failure Isolation

Each certificate is generated inside an independent `try/except` block within the Celery task. If one certificate fails:
- Its `Certificate.status` is set to `FAILED` with an `error_message`
- `Job.failed_count` is incremented
- All other certificates continue processing
- The final job status reflects partial success (`PARTIALLY_COMPLETED` if some succeeded, `FAILED` if all failed)

---

## 📁 Project Structure

```
bulk/
├── backend/                     # ⚙️ All Python Backend Code & Tests
│   ├── app/
│   │   ├── api/routes/jobs.py   # REST API routes
│   │   ├── core/config.py       # Pydantic environment configuration
│   │   ├── db/database.py       # Async & sync SQLAlchemy engines
│   │   ├── models/models.py     # ORM database models
│   │   ├── schemas/schemas.py   # Pydantic validation schemas
│   │   ├── services/
│   │   │   ├── certificate_generator.py # ReportLab PDF engine
│   │   │   └── email_service.py # Email delivery / SMTP service
│   │   ├── tasks/
│   │   │   ├── celery_app.py    # Celery configuration
│   │   │   └── generation_tasks.py # Async generation tasks
│   │   └── main.py              # FastAPI application entrypoint
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # 41 Unit and integration tests
│   ├── alembic.ini              # Migration settings
│   ├── pytest.ini               # Test configuration
│   ├── requirements.txt         # Python dependencies
│   └── README.md                # Backend docs
│
├── frontend/                    # 🎨 All Frontend Web Files
│   ├── public/
│   │   └── index.html           # Web UI Dashboard (Tailwind + Alpine.js)
│   └── README.md                # Frontend docs
│
├── certificates/                # Generated PDF storage
├── docker-compose.yml           # 5-Service Docker orchestration
├── Dockerfile                   # Multi-stage container build
├── run.sh                       # 1-click startup script (FastAPI + Celery)
├── pytest.ini                   # Root test runner config
└── .env.example                 # Environment variables template
```

---

## 🌐 Enterprise SaaS Frontend Console

The application includes an enterprise-grade Single Page Application (SPA) dashboard served directly at **`http://localhost:8000`**, inspired by **Preline** and **Flowbite** design systems:

- **Overview Dashboard**: Executive metric cards (Total Recipients, Completed Certificates, Active Background Processing, Failed Records), Recent Batches activity list, and Vector A4 Template showcase.
- **Create Batch Console**: Clean form with Event & Issuer fields, dynamic recipient row manager, 1-click *"Load Sample Batch (5 Recipients)"*, and client-side duplicate email prevention.
- **Live Job Tracker**: Real-time progress bar polling `GET /api/v1/jobs/{id}/detail` at 1.5s intervals, live metric counters, per-recipient status pills, and direct **"Download PDF"** buttons with failure diagnostics.
- **Jobs History**: Searchable session history of all submitted batch UUIDs.
- **Certificates Repository**: Aggregated downloads table with live search by recipient name or email.
- **Toast Notification System**: Global floating alerts for confirmations, copy events, and validation errors.

---

## 🚀 Setup & Running

### Option 1: 1-Click Dev Runner (Recommended for Local Dev)

```bash
cd bulk
./run.sh
```
This single command automatically starts Redis, Celery (with solo pool for macOS Python 3.14 compatibility), and FastAPI with hot-reload enabled.

### Option 2: Docker Compose (5 Microservices)

**Prerequisites**: Docker Desktop installed and running.

```bash
cd bulk
docker compose up --build

# Services available:
# Web App & Dashboard: http://localhost:8000
# Interactive Swagger Docs: http://localhost:8000/docs
# Flower Task Monitor: http://localhost:5555
```

### Option 3: Manual Virtual Environment

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Start FastAPI server
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
uvicorn app.main:app --reload --port 8000

# 5. Start Celery worker (in a separate terminal)
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
celery -A app.tasks.celery_app worker --pool=solo --loglevel=info
```

---

## 🧪 Running Tests

Tests use an **in-memory SQLite database** — no PostgreSQL or Redis required.

```bash
# Activate venv first (if running locally)
source venv/bin/activate

# Install test dependencies (included in backend/requirements.txt)
pip install -r backend/requirements.txt

# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_job_creation.py -v

# Run with coverage report only (no HTML)
pytest --cov=app --cov-report=term-missing

# Run tests matching a keyword
pytest -k "test_partial_failure"
```

**Test coverage includes**:
- ✅ Creating a generation job (success + validation)
- ✅ Input validation (missing fields, invalid email, blank name, bad date, duplicate emails)
- ✅ PDF certificate generation (file creation, PDF magic bytes, unique filenames)
- ✅ Job status / progress tracking
- ✅ Handling individual certificate failures (isolation, error messages, partial completion)
- ✅ Retrieving generated certificates
- ✅ Download endpoint guards (pending cert, 404 cases)

---

## 📡 API Reference

### Base URL: `http://localhost:8000/api/v1`

Interactive docs available at **http://localhost:8000/docs**

---

### `POST /jobs/` — Submit a bulk certificate generation request

**Request Body**:
```json
{
  "event_name": "Python Mastery Workshop",
  "issued_by": "Tech Academy",
  "recipients": [
    {
      "name": "Alice Johnson",
      "email": "alice@example.com",
      "course_name": "Advanced Python",
      "completion_date": "2024-06-15"
    },
    {
      "name": "Bob Smith",
      "email": "bob@example.com"
    }
  ]
}
```

**Response** `202 Accepted`:
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "event_name": "Python Mastery Workshop",
  "issued_by": "Tech Academy",
  "status": "pending",
  "total_count": 2,
  "message": "Job created successfully. 2 certificates will be generated in the background..."
}
```

**Validation rules**:
- `name`: required, non-blank
- `email`: required, valid email format, unique within the batch
- `completion_date`: optional, must be `YYYY-MM-DD` format

---

### `GET /jobs/{job_id}` — Get job progress

**Response** `200 OK`:
```json
{
  "id": "3fa85f64-...",
  "event_name": "Python Mastery Workshop",
  "issued_by": "Tech Academy",
  "status": "processing",
  "total_count": 2,
  "completed_count": 1,
  "failed_count": 0,
  "progress_percentage": 50.0,
  "celery_task_id": "abc-123",
  "created_at": "2024-06-15T10:00:00Z",
  "updated_at": "2024-06-15T10:00:05Z"
}
```

**Job statuses**: `pending` → `processing` → `completed` / `partially_completed` / `failed`

---

### `GET /jobs/{job_id}/detail` — Full job detail with certificates

Returns the job status plus the full list of individual certificate records (including per-recipient status and error messages for failures).

---

### `GET /jobs/{job_id}/certificates` — List all certificates

Returns array of certificate objects with `status`, `recipient_name`, `recipient_email`, and `error_message` (if failed).

---

### `GET /jobs/{job_id}/certificates/{cert_id}/download` — Download PDF

**Response**: `application/pdf` binary stream.

Returns `409 Conflict` if the certificate is not yet completed.

---

## 📊 Example: Full Workflow

```bash
# 1. Submit a job
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "Data Science Bootcamp",
    "issued_by": "DataCorp Institute",
    "recipients": [
      {"name": "Alice Johnson", "email": "alice@example.com", "completion_date": "2024-06-15"},
      {"name": "Bob Smith", "email": "bob@example.com"},
      {"name": "Carol White", "email": "carol@example.com", "course_name": "ML Fundamentals"}
    ]
  }'

# 2. Poll for status (use the job ID from step 1)
JOB_ID="<job-id-from-response>"
curl http://localhost:8000/api/v1/jobs/$JOB_ID

# 3. View full detail with per-certificate status
curl http://localhost:8000/api/v1/jobs/$JOB_ID/detail

# 4. Download a specific certificate (use cert ID from step 3)
CERT_ID="<cert-id-from-response>"
curl -O http://localhost:8000/api/v1/jobs/$JOB_ID/certificates/$CERT_ID/download
```

---

## 🌸 Monitoring with Flower

Celery Flower dashboard is available at **http://localhost:5555** when using Docker Compose. It shows:
- Active, pending, and completed tasks
- Task arguments, results, and timing
- Worker health and concurrency

---

## 🔧 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async DB URL (FastAPI) |
| `SYNC_DATABASE_URL` | `postgresql://...` | Sync DB URL (Celery) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CELERY_BROKER_URL` | Same as REDIS_URL | Celery task broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | Celery result storage |
| `CERT_STORAGE_PATH` | `./certificates` | Where PDFs are saved |
| `DEBUG` | `False` | Enable debug logging |
