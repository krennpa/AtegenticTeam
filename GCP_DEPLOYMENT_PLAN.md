# GCP Deployment Plan for Dynalunch

## Current Infrastructure Overview

### Dockerized Services
- **Backend**: FastAPI with Python 3.12, Playwright/Chromium for scraping
- **Frontend**: Next.js 14 with standalone output mode
- **Database**: SQLite (file-based, mounted volume)
- **Dependencies**: Google Cloud Vertex AI already integrated

### Key Findings

**✅ Already GCP-Ready:**
- Google Cloud credentials setup in backend config
- LangChain + Vertex AI integration (`langchain-google-vertexai`)
- Docker containers with health checks
- Next.js standalone output mode

**⚠️ Migration Required:**
- SQLite → Cloud SQL (PostgreSQL) or Firestore
- File-based storage → Cloud Storage for restaurant documents
- Service account credentials handling
- CORS origins for production URLs

---

## GCP Deployment Options

### Option 1: Cloud Run (Recommended)
**Best for:** Serverless, auto-scaling, pay-per-use

**Services:**
- **Backend**: Cloud Run service (FastAPI container)
- **Frontend**: Cloud Run service (Next.js container)
- **Database**: Cloud SQL (PostgreSQL) or Firestore
- **Storage**: Cloud Storage for scraped content
- **Secrets**: Secret Manager for credentials

**Pros:**
- Fully managed, auto-scaling
- No infrastructure management
- Cost-effective (pay only when running)
- Built-in HTTPS/SSL

**Cons:**
- Cold starts (mitigated with min instances)
- Playwright may need memory tuning

---

### Option 2: Google Kubernetes Engine (GKE)
**Best for:** Complex orchestration, high control

**Pros:**
- Full container orchestration
- Better for complex microservices
- More control over networking

**Cons:**
- Higher complexity and cost
- Requires Kubernetes expertise
- Overkill for current app size

---

### Option 3: Compute Engine + Docker Compose
**Best for:** Lift-and-shift, minimal changes

**Pros:**
- Easiest migration (use existing docker-compose)
- Full VM control

**Cons:**
- Manual scaling and management
- Higher operational overhead
- No auto-scaling

---

## Required Changes for Cloud Run (Recommended)

### 1. Database Migration

**Current:** SQLite file  
**Target:** Cloud SQL PostgreSQL

**Changes needed:**
```python
# Add to requirements.txt
psycopg2-binary>=2.9.9  # PostgreSQL driver

# Update DATABASE_URL format
DATABASE_URL=postgresql://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
```

**Files to modify:**
- `backend/requirements.txt`
- `backend/app/db/session.py` (remove SQLite-specific `check_same_thread` args)

---

### 2. Credentials Management

**Current:** File-based service account JSON  
**Target:** Workload Identity or Secret Manager

**For Cloud Run:**
- Use Workload Identity (no credentials file needed)
- Or mount secrets from Secret Manager

**Changes to `backend/app/core/config.py`:**
```python
import os

if os.getenv("K_SERVICE"):  # Cloud Run environment variable
    # Use Application Default Credentials (ADC)
    # No GOOGLE_APPLICATION_CREDENTIALS needed
    pass
else:
    # Local development - use file
    # existing logic
```

---

### 3. Storage for Restaurant Documents

**Current:** SQLite BLOB storage  
**Recommended:** Keep in database OR use Cloud Storage

**Option A: Keep in PostgreSQL** (Simplest)
- No changes needed
- PostgreSQL handles BLOB storage well

**Option B: Use Cloud Storage** (More scalable)
- Add `google-cloud-storage` to requirements
- Store document content in GCS buckets
- Store GCS URLs in database

---

### 4. Environment Configuration

**Production environment variables:**

**Backend:**
```bash
DATABASE_URL=postgresql://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
SECRET_KEY=<strong-random-key-generate-with-openssl>
CORS_ORIGINS=["https://your-frontend-url.run.app"]
GOOGLE_CLOUD_PROJECT=your-project-id
```

**Frontend:**
```bash
NEXT_PUBLIC_API_BASE_URL=https://your-backend-url.run.app
```

---

### 5. Docker Optimizations

**Backend Dockerfile:**
- Already good, but consider multi-stage build to reduce size
- Playwright chromium is heavy (~500MB) - acceptable for Cloud Run
- Consider memory allocation: 1-2GB recommended

**Frontend Dockerfile:**
- Already optimized with standalone mode ✅
- Multi-stage build already implemented ✅

---

### 6. CORS Configuration

**Update `backend/app/core/config.py`:**
```python
CORS_ORIGINS: List[str] = Field(
    default=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://your-frontend-url.run.app",  # Add production URL
    ]
)
```

---

## Deployment Artifacts Needed

### 1. Cloud Build Configuration

**Create `cloudbuild.yaml` in project root:**
```yaml
steps:
  # Build backend
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/dynalunch-backend', './backend']
  
  # Build frontend
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/dynalunch-frontend', 
           '--build-arg', 'NEXT_PUBLIC_API_BASE_URL=https://backend-$PROJECT_ID.run.app',
           './frontend']
  
  # Push images
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/dynalunch-backend']
  
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/dynalunch-frontend']

images:
  - 'gcr.io/$PROJECT_ID/dynalunch-backend'
  - 'gcr.io/$PROJECT_ID/dynalunch-frontend'
```

### 2. Cloud Run Deployment Script

**Create `deploy.sh`:**
```bash
#!/bin/bash
PROJECT_ID="your-project-id"
REGION="us-central1"

# Deploy backend
gcloud run deploy dynalunch-backend \
  --image gcr.io/$PROJECT_ID/dynalunch-backend \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars DATABASE_URL="postgresql://...",GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
  --set-secrets SECRET_KEY=dynalunch-secret-key:latest \
  --add-cloudsql-instances $PROJECT_ID:$REGION:dynalunch-db

# Deploy frontend
gcloud run deploy dynalunch-frontend \
  --image gcr.io/$PROJECT_ID/dynalunch-frontend \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars NEXT_PUBLIC_API_BASE_URL=https://dynalunch-backend-xyz.run.app
```

### 3. Terraform Configuration (Optional)

**Create `terraform/main.tf`:**
```hcl
provider "google" {
  project = var.project_id
  region  = var.region
}

# Cloud SQL PostgreSQL instance
resource "google_sql_database_instance" "main" {
  name             = "dynalunch-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-f1-micro"
    
    backup_configuration {
      enabled = true
    }
  }
}

resource "google_sql_database" "database" {
  name     = "dynalunch"
  instance = google_sql_database_instance.main.name
}

# Secret Manager for sensitive data
resource "google_secret_manager_secret" "secret_key" {
  secret_id = "dynalunch-secret-key"
  
  replication {
    automatic = true
  }
}

# Cloud Run services (backend)
resource "google_cloud_run_service" "backend" {
  name     = "dynalunch-backend"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/dynalunch-backend"
        
        resources {
          limits = {
            memory = "2Gi"
            cpu    = "2"
          }
        }
      }
    }
  }
}

# Cloud Run services (frontend)
resource "google_cloud_run_service" "frontend" {
  name     = "dynalunch-frontend"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/dynalunch-frontend"
      }
    }
  }
}
```

---

## Cost Estimates (Monthly)

### Cloud Run (Small Scale - <1000 users)
- **Backend**: ~$10-30 (depends on usage)
- **Frontend**: ~$5-15
- **Cloud SQL** (db-f1-micro): ~$7-15
- **Cloud Storage**: ~$1-5
- **Vertex AI**: Pay per token (~$5-20)
- **Total: ~$30-85/month**

### With Sustained Usage (1000-10000 users)
- Backend: ~$50-150
- Frontend: ~$20-50
- Cloud SQL (db-g1-small): ~$25-50
- Total: ~$100-250/month

---

## Migration Checklist

### Phase 1: Database Migration
- [ ] Create Cloud SQL PostgreSQL instance
- [ ] Update `requirements.txt` with `psycopg2-binary`
- [ ] Update `DATABASE_URL` in config
- [ ] Remove SQLite-specific connection args
- [ ] Test database connection locally (Cloud SQL Proxy)
- [ ] Create migration script for existing SQLite data
- [ ] Run database migrations

### Phase 2: Credentials & Secrets
- [ ] Create service account for Cloud Run
- [ ] Enable Workload Identity on Cloud Run
- [ ] Grant Vertex AI permissions to service account
- [ ] Store SECRET_KEY in Secret Manager
- [ ] Update credential loading logic for Cloud Run
- [ ] Test with Application Default Credentials locally

### Phase 3: Code Updates
- [ ] Update CORS origins for production URLs
- [ ] Add Cloud Run environment detection
- [ ] Update health check endpoint (ensure it works)
- [ ] Add graceful shutdown handling
- [ ] Update logging to use Cloud Logging format

### Phase 4: Docker & Build
- [ ] Create `cloudbuild.yaml`
- [ ] Test Docker builds locally
- [ ] Enable Cloud Build API
- [ ] Enable Artifact Registry API
- [ ] Push images to Artifact Registry
- [ ] Verify image sizes and startup times

### Phase 5: Cloud Run Deployment
- [ ] Deploy backend service
- [ ] Configure environment variables
- [ ] Set up Cloud SQL connection (VPC connector)
- [ ] Test backend endpoints
- [ ] Deploy frontend service
- [ ] Update frontend API URL
- [ ] Test end-to-end flow

### Phase 6: Domain & SSL (Optional)
- [ ] Configure custom domain for backend
- [ ] Configure custom domain for frontend
- [ ] Set up Cloud Load Balancer (if needed)
- [ ] Configure SSL certificates

### Phase 7: Testing & Monitoring
- [ ] Test authentication flow
- [ ] Test restaurant scraping (Playwright in Cloud Run)
- [ ] Test AI decision agent (Vertex AI)
- [ ] Set up Cloud Logging
- [ ] Set up Cloud Monitoring dashboards
- [ ] Configure alerting policies
- [ ] Load testing with realistic traffic
- [ ] Security audit

### Phase 8: Production Readiness
- [ ] Set up CI/CD pipeline (Cloud Build triggers)
- [ ] Configure staging environment
- [ ] Set up database backups
- [ ] Document deployment process
- [ ] Create rollback procedure
- [ ] Set up cost monitoring and budgets

---

## Quick Start Commands

### Local Development with Cloud SQL Proxy
```bash
# Install Cloud SQL Proxy
gcloud components install cloud-sql-proxy

# Start proxy
cloud-sql-proxy your-project:us-central1:dynalunch-db

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://user:pass@localhost:5432/dynalunch
```

### Build and Deploy
```bash
# Build with Cloud Build
gcloud builds submit --config cloudbuild.yaml

# Deploy backend
gcloud run deploy dynalunch-backend \
  --image gcr.io/PROJECT_ID/dynalunch-backend \
  --region us-central1 \
  --allow-unauthenticated

# Deploy frontend
gcloud run deploy dynalunch-frontend \
  --image gcr.io/PROJECT_ID/dynalunch-frontend \
  --region us-central1 \
  --allow-unauthenticated
```

### Database Migration
```bash
# Export SQLite data
sqlite3 backend/data/dynalunch.db .dump > backup.sql

# Convert to PostgreSQL format (manual or use tool)
# Import to Cloud SQL
psql -h /cloudsql/PROJECT:REGION:INSTANCE -U postgres -d dynalunch < converted.sql
```

---

## Troubleshooting

### Common Issues

**1. Playwright fails in Cloud Run**
- Increase memory to 2Gi
- Ensure chromium dependencies are installed
- Check container logs for missing libraries

**2. Cold starts are slow**
- Set minimum instances to 1
- Optimize Docker image size
- Use startup probes

**3. Database connection fails**
- Verify Cloud SQL connection name
- Check VPC connector configuration
- Ensure service account has Cloud SQL Client role

**4. CORS errors**
- Update CORS_ORIGINS with production URLs
- Check Cloud Run service URLs
- Verify frontend is using correct API URL

---

## Security Considerations

1. **Never commit credentials** - Use Secret Manager
2. **Use IAM roles** - Principle of least privilege
3. **Enable VPC** - Private Cloud SQL connection
4. **Rate limiting** - Add Cloud Armor or API Gateway
5. **Authentication** - Keep JWT secure, consider refresh tokens
6. **Audit logging** - Enable Cloud Audit Logs
7. **Vulnerability scanning** - Enable Container Analysis

---

## Next Steps

Choose one of the following approaches:

1. **Quick Deploy** - Manual deployment using gcloud CLI
2. **IaC Approach** - Terraform for reproducible infrastructure
3. **CI/CD Pipeline** - Automated deployments with Cloud Build triggers

Recommended: Start with Quick Deploy, then migrate to Terraform + CI/CD.
