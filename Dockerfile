FROM python:3.11-slim

# Install system dependencies for PDF generation
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app/backend
RUN mkdir -p /app/certificates

EXPOSE 8000

