# 📜 Bulk Certificate Generator

A high-throughput, fault-tolerant enterprise solution for generating personalized vector PDF certificates in bulk. Built with **FastAPI**, **PostgreSQL**, **Celery**, **Redis**, and **ReportLab**, featuring an interactive web dashboard for real-time progress tracking and downloads.

---

## 📑 Table of Contents

- [🏛️ System Architecture](#️-system-architecture)
- [💡 Important Implementation & Design Decisions](#-important-implementation--design-decisions)
- [📁 Project Structure](#-project-structure)
- [⚙️ How to Set Up the Project](#️-how-to-set-up-the-project)
- [🚀 How to Run the Application](#-how-to-run-the-application)
- [📤 How to Submit a Certificate Generation Request](#-how-to-submit-a-certificate-generation-request)
- [📥 How to Retrieve Generated Certificates](#-how-to-retrieve-generated-certificates)
- [🧪 How to Run Tests](#-how-to-run-tests)
- [🌸 Task Monitoring with Flower](#-task-monitoring-with-flower)
- [🔧 Environment Variables Reference](#-environment-variables-reference)
- [🎁 Optional & Extended Improvements](#-optional--extended-improvements)
---

## 🏛️ System Architecture

### Visualized Architecture Diagram

```mermaid
graph TD
    subgraph ClientLayer ["1. Client & Presentation Layer"]
        UI["Web Dashboard (Tailwind CSS + Alpine.js)"]
        CLI["REST Clients / cURL / Postman / Third-party Apps"]
    end

    subgraph APILayer ["2. API & Ingestion Layer (FastAPI)"]
        API["FastAPI Web Server (Port 8000)"]
        Validator["Pydantic Validation (JobCreate & RecipientSchema)"]
        Router["Jobs Router (/api/v1/jobs)"]
    end

    subgraph StorageQueue ["3. Data & Message Infrastructure"]
        DB[("PostgreSQL Database (AsyncPG & Psycopg2)")]
        Redis[("Redis Message Broker & Celery Result Backend")]
    end

    subgraph WorkerLayer ["4. Background Worker Layer (Celery)"]
        Worker["Celery Background Worker (Solo / Prefork Pool)"]
        PDFGen["ReportLab Vector PDF Generation Engine"]
        EmailSvc["Email Delivery Service (Optional SMTP)"]
    end

    subgraph StorageLayer ["5. Artifact Storage & Monitoring"]
        Storage["Local PDF Storage (/certificates/*.pdf)"]
        Flower["Flower Worker Monitor (Port 5555)"]
    end

    UI -->|"HTTP Request / 1.5s Polling"| API
    CLI -->|"POST /api/v1/jobs/"| API
    API --> Validator
    Validator --> Router
    Router -->|"1. Insert Job & Recipients (Status: PENDING)"| DB
    Router -->|"2. Dispatch Task (job_id)"| Redis
    Router -.->|"3. Return 202 Accepted (job_id)"| UI

    Redis -->|"Consume Batch Task"| Worker
    Worker -->|"Update Job Status -> PROCESSING"| DB
    Worker -->|"Render Certificate Canvas"| PDFGen
    PDFGen -->|"Write .pdf to Disk"| Storage
    Worker -->|"Update Record -> COMPLETED / FAILED"| DB
    Worker -.->|"Send Notification Email (Optional)"| EmailSvc
    Worker -->|"Update Job -> COMPLETED / PARTIAL / FAILED"| DB
    Worker -->|"Stream Task Metrics"| Flower
    UI -->|"GET /api/v1/jobs/{id}/certificates/{cid}/download"| API
    API -->|"Stream FileResponse (application/pdf)"| Storage
```

### End-to-End Data Flow

1. **Ingestion**: A client sends a batch request containing event details and recipient information to `POST /api/v1/jobs/`.
2. **Validation & Persistence**: FastAPI validates input schemas using Pydantic, creates the `Job` and associated `Certificate` rows in PostgreSQL in `pending` state, and commits the transaction.
3. **Decoupled Dispatch**: FastAPI dispatches an asynchronous background task `generate_bulk_certificates` to Redis and immediately returns an HTTP `202 Accepted` response with the `job_id`.
4. **Asynchronous Execution**: A dedicated Celery worker picks up the job from the Redis queue and transitions the job to `processing`.
5. **PDF Rendering**: The worker iterates over each recipient, invoking the ReportLab PDF engine to generate a high-resolution, vector-based A4 landscape certificate stored in `./certificates/`.
6. **Live Monitoring**: Clients poll `GET /api/v1/jobs/{job_id}/detail` to observe live progress counters, completion percentages, and recipient status pills.
7. **Retrieval**: Completed certificates can be directly downloaded via `GET /api/v1/jobs/{job_id}/certificates/{cert_id}/download` or accessed directly on the local file system.

---

## 💡 Important Implementation & Design Decisions

### 1. Asynchronous Background Processing (Celery + Redis)
- **Problem**: Generating hundreds or thousands of high-resolution PDF certificates synchronously within an HTTP request would cause browser timeouts, gateway `504` errors, and lock HTTP worker threads.
- **Decision**: All PDF rendering is offloaded to Celery background workers via a Redis queue.
- **Benefits**:
  - The API responds in milliseconds (`202 Accepted`) regardless of batch size.
  - Workers can scale horizontally across multiple containers or servers.
  - API servers remain responsive to incoming user traffic.

### 2. Failure Isolation & Graceful Degradation
- **Problem**: In batch operations, one corrupt recipient (e.g., character encoding issues, disk write glitch) should not terminate the entire batch.
- **Decision**: Each individual certificate is generated within an isolated `try/except` block.
- **Benefits**:
  - If certificate generation fails for recipient #42, its individual status is marked as `FAILED` with an informative `error_message`, and `failed_count` is incremented.
  - Processing immediately continues for recipient #43 without interruption.
  - The final job status accurately reflects outcomes: `completed` (all succeeded), `partially_completed` (some failed), or `failed` (all failed).

### 3. Dual Database Engines (Async FastAPI + Sync Celery)
- **Problem**: FastAPI operates with non-blocking async coroutines (`asyncpg`), whereas standard Celery tasks run synchronously.
- **Decision**: The database layer exposes two connection engines configured in `app/db/database.py`:
  - `async_engine` (`postgresql+asyncpg://`): Powers FastAPI routes for non-blocking I/O.
  - `sync_engine` (`postgresql://`): Powers Celery tasks with standard thread-safe SQLAlchemy sessions.
- **Benefits**: Eliminates event-loop conflicts within Celery worker threads while maximizing FastAPI throughput.

### 4. Vector PDF Generation via ReportLab
- **Problem**: Headless browser solutions (e.g., Puppeteer, wkhtmltopdf) require heavy OS packages, large container images, and consume substantial memory per page.
- **Decision**: Implemented pure-Python vector PDF rendering using **ReportLab**.
- **Benefits**:
  - Zero heavy binary dependencies (no Chromium, no webkit).
  - Sub-50ms render times per certificate.
  - Generates crisp vector lines, professional borders, custom color palettes, and embedded fonts.

### 5. Hermetic, Zero-External-Dependency Test Suite
- **Problem**: Integration tests that depend on live Redis and PostgreSQL servers are brittle and slow in CI/CD pipelines.
- **Decision**: Configured pytest with an in-memory SQLite database (`sqlite+aiosqlite`) and Celery in memory mode (`memory://`).
- **Benefits**:
  - All 41 unit and integration tests execute hermetically in under 5 seconds.
  - Automatic teardown fixtures clean up test artifacts on disk upon session completion.

---

## 📁 Project Structure

```
bulk/
├── backend/                     # ⚙️ Python Backend Services & Test Suite
│   ├── app/                     # Application source code
│   │   ├── api/routes/jobs.py   # REST API endpoints (create, status, download)
│   │   ├── core/config.py       # Pydantic Settings & environment validation
│   │   ├── db/database.py       # Async & Sync SQLAlchemy database configurations
│   │   ├── models/models.py     # SQLAlchemy ORM models (Job, Certificate)
│   │   ├── schemas/schemas.py   # Pydantic schemas & request validation
│   │   ├── services/
│   │   │   ├── certificate_generator.py # ReportLab PDF rendering engine
│   │   │   └── email_service.py # Email delivery & notification service
│   │   ├── tasks/
│   │   │   ├── celery_app.py    # Celery application & broker setup
│   │   │   └── generation_tasks.py # Background task execution & isolation
│   │   └── main.py              # FastAPI entrypoint & frontend static mounting
│   ├── alembic/                 # Alembic database migration scripts
│   ├── alembic.ini              # Alembic migration configuration
│   ├── tests/                   # Automated test suite (41 tests)
│   ├── requirements.txt         # Production & development Python dependencies
│   ├── pytest.ini               # Pytest config for backend test runs
│   └── README.md                # Backend documentation
│
├── frontend/                    # 🎨 Single Page Application (SPA) Web Console
│   ├── public/
│   │   └── index.html           # Dashboard UI (Tailwind CSS + Alpine.js + Lucide)
│   └── README.md                # Frontend documentation
│
├── certificates/                # 📄 Output directory where generated PDFs are saved
│   └── .gitkeep                 # Ensures directory exists in version control
├── docker-compose.yml           # 🐳 5-Microservice Docker Compose configuration
├── Dockerfile                   # 🐳 Multi-service container build definition
├── run.sh                       # 🚀 1-Click local development startup script
├── pytest.ini                   # 🧪 Root pytest runner configuration
├── .env.example                 # 📋 Environment variables template
├── .gitignore                   # 🛡️ Ignores secrets, caches, logs, and artifacts
└── README.md                    # 📖 Project documentation
```

---

## ⚙️ How to Set Up the Project

### Prerequisites
- **Python**: 3.11 or higher (3.11, 3.12, 3.13, or 3.14)
- **Redis**: 6.0+ (required for local background task queue)
- **PostgreSQL**: 14+ (optional for local SQLite testing, recommended for production)
- **Docker & Docker Compose**: (optional, for containerized execution)

### Step 1: Clone the Repository
```bash
git clone https://github.com/siddharthq26/Bulk_Certificate_Generator.git
cd Bulk_Certificate_Generator
```

### Step 2: Configure Environment Variables
Copy the template configuration file to create your active `.env`:
```bash
cp .env.example .env
```
Default configuration values for local development:
```env
APP_NAME="Bulk Certificate Generator"
APP_VERSION="1.0.0"
DEBUG=True

# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/bulk_cert_db
SYNC_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bulk_cert_db

# Message Broker & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# PDF File Storage
CERT_STORAGE_PATH=./certificates
```

### Step 3: Install Dependencies
Create and activate a virtual environment, then install requirements:
```bash
python3 -m venv venv
source venv/bin/activate       # macOS / Linux
# venv\Scripts\activate        # Windows

pip install -r backend/requirements.txt
```

---

## 🚀 How to Run the Application

### Option 1: 1-Click Dev Runner (Recommended for Local Dev)
The repository includes an automated startup script `run.sh` that checks Redis, starts the Celery worker in the background, and launches FastAPI with live reload:

```bash
chmod +x run.sh
./run.sh
```

### Option 2: Docker Compose (5 Microservices)
Run all 5 services (FastAPI, Celery worker, Flower, PostgreSQL, Redis) with a single command:

```bash
docker compose up --build
```
*To stop the containers, press `Ctrl+C` or run `docker compose down`.*

### Option 3: Manual Startup (Separate Terminals)

**Terminal 1 — Start Redis**:
```bash
# macOS (Homebrew)
brew services start redis

# Linux (systemd)
sudo systemctl start redis
```

**Terminal 2 — Start Celery Worker**:
```bash
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
celery -A app.tasks.celery_app worker --pool=solo --loglevel=info
```
*(Note: `--pool=solo` is recommended for macOS Python 3.14 compatibility; use `--concurrency=4` on Linux).*

**Terminal 3 — Start FastAPI Server**:
```bash
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 🌐 Service URL Reference

| Service | URL | Description |
|---|---|---|
| **Web Console Dashboard** | [http://localhost:8000](http://localhost:8000) | Interactive SPA dashboard for batch creation & tracking |
| **Swagger Interactive Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | OpenAPI specification & test sandbox |
| **ReDoc Documentation** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative formatted API specification |
| **API Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Uptime and service status probe |
| **Flower Worker Monitor** | [http://localhost:5555](http://localhost:5555) | Real-time Celery queue and worker health |

---

## 📤 How to Submit a Certificate Generation Request

### Method A: Via Web Console (Interactive UI)
1. Open your browser and navigate to **`http://localhost:8000`**.
2. Click on the **"Create Batch"** tab in the sidebar.
3. Enter the **Event Name** (e.g., `Python Mastery Bootcamp`) and **Issuer Name** (e.g., `Tech Institute`).
4. Either:
   - Click **"Load Sample Batch (5 Recipients)"** for instant one-click test data, OR
   - Click **"+ Add Recipient"** to manually enter names and emails.
5. Click **"🚀 Launch Generation Job"**.
6. The dashboard will automatically transition to the **Live Job Tracker** view.

---

### Method B: Via REST API (`POST /api/v1/jobs/`)

Send an HTTP `POST` request with a JSON payload to `/api/v1/jobs/`:

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "Full Stack Engineering Summit",
    "issued_by": "Global Tech Council",
    "recipients": [
      {
        "name": "Siddhartha Sharma",
        "email": "siddharth@example.com",
        "course_name": "Cloud Native Architecture",
        "completion_date": "2026-10-10"
      },
      {
        "name": "Ananya Patel",
        "email": "ananya@example.com",
        "course_name": "Kubernetes & Microservices",
        "completion_date": "2026-10-10"
      },
      {
        "name": "Rahul Verma",
        "email": "rahul@example.com",
        "course_name": "FastAPI & Distributed Systems",
        "completion_date": "2026-10-10"
      }
    ]
  }'
```

#### Expected Response (`202 Accepted`):
```json
{
  "id": "7b8f9e12-3456-4abc-9def-123456789abc",
  "event_name": "Full Stack Engineering Summit",
  "issued_by": "Global Tech Council",
  "status": "pending",
  "total_count": 3,
  "completed_count": 0,
  "failed_count": 0,
  "progress_percentage": 0.0,
  "celery_task_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "message": "Job created successfully. 3 certificates will be generated in the background. Use the job ID to track progress.",
  "created_at": "2026-10-10T16:00:00Z",
  "updated_at": "2026-10-10T16:00:00Z"
}
```

#### Validation Rules:
- `event_name` & `issued_by`: Required, non-empty strings.
- `recipients`: Required list containing between 1 and 5,000 recipients.
- `recipients[].name`: Required, non-blank string.
- `recipients[].email`: Required valid email format; must be unique within the batch.
- `recipients[].completion_date`: Optional string in `YYYY-MM-DD` format.

---

## 📥 How to Retrieve Generated Certificates

### Method A: Via Web Console
1. On the **Live Job Tracker** screen, observe the progress bar update in real time as certificates are generated.
2. Once a recipient's certificate reaches `COMPLETED` status, click the blue **"Download PDF"** button next to their name.
3. You can also view all generated certificates under the **"Certificates Repository"** tab, where you can search by recipient name or email.

---

### Method B: Via REST API

#### 1. Check Job Progress
Poll the job status endpoint using the UUID returned from the creation request:
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/{job_id}"
```
**Response (`200 OK`)**:
```json
{
  "id": "7b8f9e12-3456-4abc-9def-123456789abc",
  "status": "completed",
  "total_count": 3,
  "completed_count": 3,
  "failed_count": 0,
  "progress_percentage": 100.0,
  "celery_task_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "created_at": "2026-10-10T16:00:00Z",
  "updated_at": "2026-10-10T16:00:05Z"
}
```
*Possible job statuses*: `pending` ➔ `processing` ➔ `completed` / `partially_completed` / `failed`.

---

#### 2. Inspect Full Job Details & Certificate IDs
Retrieve the job details including recipient records and unique certificate UUIDs:
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/{job_id}/detail"
```
**Response Snippet (`200 OK`)**:
```json
{
  "id": "7b8f9e12-3456-4abc-9def-123456789abc",
  "event_name": "Full Stack Engineering Summit",
  "status": "completed",
  "certificates": [
    {
      "id": "a1b2c3d4-0000-1111-2222-333344445555",
      "recipient_name": "Siddhartha Sharma",
      "recipient_email": "siddharth@example.com",
      "status": "completed",
      "file_path": "/app/certificates/certificate_siddharth_example.com_18b3608c.pdf",
      "error_message": null
    }
  ]
}
```

---

#### 3. Download the PDF Binary
Download the generated PDF certificate directly using its `cert_id`:
```bash
curl -O -J "http://localhost:8000/api/v1/jobs/{job_id}/certificates/{cert_id}/download"
```
- **Response**: `application/pdf` binary stream with `Content-Disposition: attachment; filename="certificate_<email>_<id>.pdf"`.
- If the certificate is still `pending` or `processing`, the endpoint returns `409 Conflict`.
- If generation failed for that recipient, the endpoint returns `400 Bad Request` with the specific error message.

---

### Method C: Direct Local Storage Access
Generated PDF files are stored on disk in the directory specified by `CERT_STORAGE_PATH` (defaults to `./certificates/`):
```bash
ls -lh certificates/
```
Output:
```
certificate_siddharth_example.com_18b3608c.pdf
certificate_ananya_example.com_9cc25c01.pdf
certificate_rahul_example.com_469581b7.pdf
```

---

## 🧪 How to Run Tests

The test suite contains **41 automated unit and integration tests** testing validation rules, background task processing, PDF rendering, email dispatching, and failure isolation. Tests run hermetically with an in-memory SQLite database without requiring Redis or PostgreSQL.

### Run All Tests
```bash
source venv/bin/activate
pytest
```

### Run with Terminal Coverage Report
```bash
pytest --cov=app --cov-report=term-missing
```

### Run a Specific Test Module
```bash
# Test job creation & validation
pytest backend/tests/test_job_creation.py -v

# Test PDF certificate generator
pytest backend/tests/test_certificate_generation.py -v

# Test background task processing & failure isolation
pytest backend/tests/test_generation_task.py -v
```

### Run Matching Keywords
```bash
pytest -k "test_partial_failure"
```

### Test Coverage Highlights

| Module | Tested Behaviors |
|---|---|
| `test_job_creation.py` | Valid batch creation, single & large batch submissions, missing event name, empty recipients, invalid email, duplicate email rejection. |
| `test_certificate_generation.py` | PDF file creation, valid magic bytes (`%PDF-`), non-empty file size, special character encoding in recipient names, unique filenames. |
| `test_generation_task.py` | Task completion, failure isolation (one failing recipient does not stop others), error message capture, download endpoint guards. |
| `test_job_status.py` | Status polling, UUID validation, 404 handling, full detail responses. |
| `test_email_service.py` | SMTP dispatching, simulation mode fallback when SMTP is not configured. |

---

## 🌸 Task Monitoring with Flower

When running with Docker Compose or when starting Flower manually:
```bash
celery -A app.tasks.celery_app flower --port=5555
```
Access the dashboard at **`http://localhost:5555`** to observe:
- **Active / Succeeded / Failed Tasks**: Real-time counters of all background tasks.
- **Task Arguments & Return Values**: Detailed payloads for each task execution.
- **Worker Health & Concurrency**: Monitored CPU, memory, and pool state.

---

## 🔧 Environment Variables Reference

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_NAME` | `str` | `Bulk Certificate Generator` | Display name of the application |
| `APP_VERSION` | `str` | `1.0.0` | Application semantic version |
| `DEBUG` | `bool` | `False` | Enables debug log levels and detailed stack traces |
| `DATABASE_URL` | `str` | `postgresql+asyncpg://...` | Async PostgreSQL database connection string (FastAPI) |
| `SYNC_DATABASE_URL` | `str` | `postgresql://...` | Sync PostgreSQL database connection string (Celery) |
| `REDIS_URL` | `str` | `redis://localhost:6379/0` | Redis instance connection string |
| `CELERY_BROKER_URL` | `str` | `redis://localhost:6379/0` | Celery broker URL for message queue dispatch |
| `CELERY_RESULT_BACKEND` | `str` | `redis://localhost:6379/1` | Celery backend for task state and results |
| `CERT_STORAGE_PATH` | `str` | `./certificates` | Absolute or relative directory path for PDF storage |
| `SMTP_HOST` | `str` | `None` | (Optional) SMTP host for email delivery |
| `SMTP_PORT` | `int` | `587` | (Optional) SMTP port |
| `SMTP_USER` | `str` | `None` | (Optional) SMTP username |
| `SMTP_PASSWORD` | `str` | `None` | (Optional) SMTP password |
| `SMTP_FROM_EMAIL` | `str` | `certificates@example.com` | (Optional) From email address |

---

---

### 🎁 Optional & Extended Improvements

> **Prior Experience & Architectural References**
>
> I previously designed and built the [**Certification-Automation-n8n-Workflow**](https://github.com/siddharthq26/Certification-Automation-n8n-Workflow) project, which automated certificate generation and distribution using **n8n, Google Sheets, Google Drive, and Gmail**.
>
> While architecting this **Bulk Certificate Generator**, I drew functional inspiration and domain knowledge from that project, particularly around automated certificate generation, recipient management, email delivery, and persistent artifact storage. I evolved these concepts into a scalable, code-first backend architecture using **FastAPI, Celery, Redis, PostgreSQL, and ReportLab**, with asynchronous processing and individual certificate failure isolation.

---

> **Optional**
>
> These improvements represent potential extensions to the platform. They are not required for the core functionality and should not take priority over completing or maintaining existing features.

| # | Optional Improvement | Implementation in This Project | Reference from Previous Project ([Certification-Automation-n8n-Workflow](https://github.com/siddharthq26/Certification-Automation-n8n-Workflow)) | Status |
|---|---|---|---|---|
| **1** | **Automated Email Delivery (SMTP Service)** | An `EmailService` (`backend/app/services/email_service.py`) supports certificate email delivery, including PDF attachments and a simulation fallback, as implemented in the existing codebase. | **Direct Reference:** Inspired by the Gmail distribution node that delivered personalized certificates to recipients. | Implemented |
| **2** | **Enterprise Web Console (SPA Dashboard)** | Responsive dashboard built with Tailwind CSS and Alpine.js, featuring dynamic recipient rows, a sample batch loader, live progress polling, and PDF download links. | **Evolution:** Extends the workflow-based project with an interactive web dashboard for submitting and monitoring certificate-generation jobs. | Implemented |
| **3** | **Background Task Monitoring (Flower)** | Flower provides visibility into Celery workers and task execution through a monitoring dashboard on port `5555` when using Docker Compose. | **Direct Reference:** Inspired by the visual workflow execution and debugging capabilities available in n8n. | Implemented |
| **4** | **Dynamic Certificate Metadata and Categories** | The PDF generation workflow supports available metadata such as event names, course titles, completion dates, and recipient-specific certificate details. | **Direct Reference:** Inspired by conditional workflow routing for different certificate categories and templates. | Partially Implemented / Extensible |
| **5** | **Cloud Storage Integration (Google Drive / Amazon S3 / Cloudflare R2)** | Generated PDFs are currently stored locally under the configured certificate storage path. Cloud storage integration could be added for off-site storage and archival. | **Direct Reference:** Inspired by the Google Drive upload step used to archive generated certificates. | Planned |
| **6** | **Spreadsheet and Webhook Ingestion** | The existing bulk API can serve as an integration point for future ingestion from Google Sheets or external webhooks. | **Direct Reference:** Inspired by the Google Sheets trigger that initiated certificate generation from spreadsheet data. | Planned |
| **7** | **Certificate Verification with QR Codes** | A future enhancement could embed QR codes in PDFs and provide an authenticity-verification endpoint backed by persisted certificate records. | **Extension:** Builds on the broader digital credentialing concept by making issued certificates easier to verify. | Planned |

---
