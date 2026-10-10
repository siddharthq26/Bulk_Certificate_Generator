# ⚙️ Backend — Bulk Certificate Engine

A production-grade Python backend built with **FastAPI**, **PostgreSQL**, **Celery**, **Redis**, and **ReportLab**.

## 📁 Directory Structure
```
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── jobs.py          # REST endpoints (Create job, status, detail, download)
│   ├── core/
│   │   └── config.py            # Pydantic environment configuration
│   ├── db/
│   │   └── database.py          # Dual engine setup (Async for FastAPI, Sync for Celery)
│   ├── models/
│   │   └── models.py            # SQLAlchemy ORM models (GenerationJob, Certificate)
│   ├── schemas/
│   │   └── schemas.py           # Pydantic schemas & input validators
│   ├── services/
│   │   ├── certificate_generator.py # ReportLab PDF rendering engine
│   │   └── email_service.py     # SMTP & mock email delivery
│   ├── tasks/
│   │   ├── celery_app.py        # Celery broker & result backend config
│   │   └── generation_tasks.py  # Asynchronous background task with failure isolation
│   └── main.py                  # FastAPI app factory & static file mounting
├── alembic/                     # Database migrations
├── tests/                       # 41 unit & integration tests (100% passing)
├── alembic.ini                  # Migration config
├── pytest.ini                   # Test runner configuration
└── requirements.txt             # Python dependencies
```

## 🧪 Running Tests
```bash
# From project root or backend/
pytest
```
