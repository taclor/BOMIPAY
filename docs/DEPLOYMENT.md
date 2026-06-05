# BomiPay Deployment Guide

Complete deployment instructions for local development, staging, and production environments.

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 16 (or use Docker)
- Redis 8 (or use Docker)

### Setup

**1. Clone Repository**
```bash
git clone https://github.com/yourorg/bomipay
cd bomipay
```

**2. Backend Setup**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # Linux/Mac

pip install -e .
```

**3. Frontend Setup**
```bash
cd bomipay-website
npm install
cd ..
```

**4. Environment Configuration**
```bash
# Copy example env files
cp .env.example .env
cp bomipay-website/.env.local.example bomipay-website/.env.local
```

Edit `.env` with your local settings:
```bash
BOMIPAY_ENV=development
DATABASE_URL=postgresql+asyncpg://bomipay:changeme@localhost:5433/bomipay
REDIS_URL=redis://localhost:6380/0
SECRET_KEY=your-random-32-character-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_SECONDS=900
JWT_REFRESH_TOKEN_EXPIRE_SECONDS=604800
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
```

**5. Start Services**
```bash
# Terminal 1: Start Docker services (PostgreSQL, Redis)
docker-compose up -d

# Terminal 2: Run migrations
python -m alembic upgrade heads

# Terminal 3: Start backend
python -m uvicorn bomipay.main:app --reload

# Terminal 4: Start frontend
cd bomipay-website
npm run dev
```

Access at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1
- API Docs: http://localhost:8000/docs

### Database Migrations

```bash
# View migration status
alembic current

# Create new migration (auto-detect schema changes)
alembic revision --autogenerate -m "add user table"

# Apply pending migrations
alembic upgrade heads

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade ae1027a6acf
```

---

## Staging Deployment

Staging is a production-like environment for testing before release.

### Infrastructure Requirements

- Ubuntu 22.04+ server (e.g., AWS EC2 t3.large or equivalent)
- PostgreSQL 16 (managed or self-hosted)
- Redis 8 (managed or self-hosted)
- SSL certificate (Let's Encrypt free)
- Domain name
- Nginx reverse proxy

### Deployment Steps

**1. Server Preparation**
```bash
# SSH into staging server
ssh ubuntu@staging.bomipay.com

# Update system
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm git curl

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**2. Clone Repository**
```bash
cd /opt
sudo git clone https://github.com/yourorg/bomipay
sudo chown -R ubuntu:ubuntu bomipay
cd bomipay
```

**3. Backend Deployment**
```bash
python3.11 -m venv .venv
.venv/bin/activate
pip install -e .

# Create staging .env
cp .env.example .env
# Edit .env with staging credentials and database URL
nano .env
```

**4. Frontend Build**
```bash
cd bomipay-website
npm install
npm run build
cd ..
```

**5. Run Migrations**
```bash
.venv/bin/python -m alembic upgrade heads
```

**6. Start Services with Systemd**

Create `/etc/systemd/system/bomipay-api.service`:
```ini
[Unit]
Description=BomiPay FastAPI Backend
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=ubuntu
WorkingDirectory=/opt/bomipay
ExecStart=/opt/bomipay/.venv/bin/uvicorn bomipay.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/bomipay-celery.service`:
```ini
[Unit]
Description=BomiPay Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=ubuntu
WorkingDirectory=/opt/bomipay
ExecStart=/opt/bomipay/.venv/bin/celery -A bomipay.tasks worker -l info --logfile=/var/log/celery/bomipay.log
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bomipay-api bomipay-celery
sudo systemctl start bomipay-api bomipay-celery
```

**7. Configure Nginx**

Create `/etc/nginx/sites-available/bomipay-staging`:
```nginx
upstream backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name staging.bomipay.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name staging.bomipay.com;

    ssl_certificate /etc/letsencrypt/live/staging.bomipay.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/staging.bomipay.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable and test:
```bash
sudo ln -s /etc/nginx/sites-available/bomipay-staging /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**8. SSL Certificate (Let's Encrypt)**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d staging.bomipay.com
sudo systemctl restart nginx
```

**9. Health Checks**
```bash
# Check API health
curl https://staging.bomipay.com/api/v1/health

# Check logs
journalctl -u bomipay-api -f
journalctl -u bomipay-celery -f
```

---

## Production Deployment

Production requires high availability, security hardening, and monitoring.

### Architecture

- **Load Balancer:** AWS ALB or Nginx with multiple backend servers
- **Database:** AWS RDS PostgreSQL 16 (Multi-AZ)
- **Cache:** AWS ElastiCache Redis 8
- **Object Storage:** AWS S3 (for file uploads)
- **CDN:** CloudFront (optional, for static assets)
- **Monitoring:** CloudWatch, Prometheus, optional DataDog
- **Secrets Manager:** AWS Secrets Manager

### Deployment

**1. Infrastructure as Code (Terraform)**

```hcl
# variables.tf
variable "environment" { default = "production" }
variable "db_password" { sensitive = true }

# main.tf
provider "aws" { region = "us-east-1" }

# RDS PostgreSQL
resource "aws_db_instance" "bomipay" {
  identifier          = "bomipay-prod"
  engine              = "postgres"
  engine_version      = "16"
  instance_class      = "db.t4g.large"
  allocated_storage   = 100
  multi_az            = true
  publicly_accessible = false
  password            = var.db_password
  # ... additional config
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "bomipay" {
  cluster_id           = "bomipay-prod"
  engine               = "redis"
  node_type            = "cache.t4g.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  # ... additional config
}

# ECS Cluster for container orchestration
resource "aws_ecs_cluster" "bomipay" {
  name = "bomipay-prod"
  # ... additional config
}
```

**2. Docker Image Build & Registry**

```bash
# Build image
docker build -t bomipay:1.0.0 -f Dockerfile .

# Tag for AWS ECR
docker tag bomipay:1.0.0 123456789012.dkr.ecr.us-east-1.amazonaws.com/bomipay:1.0.0

# Push to registry
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/bomipay:1.0.0
```

**3. Environment Variables (AWS Secrets Manager)**

```bash
aws secretsmanager create-secret \
  --name bomipay/prod \
  --secret-string '{
    "SECRET_KEY": "your-secret-key",
    "DATABASE_URL": "postgresql+asyncpg://user:pass@rds-endpoint:5432/bomipay",
    "REDIS_URL": "redis://elasticache-endpoint:6379/0",
    "CORS_ALLOWED_ORIGINS": "https://bomipay.com,https://app.bomipay.com",
    "JWT_ACCESS_TOKEN_EXPIRE_SECONDS": "900",
    "SENTRY_DSN": "your-sentry-dsn",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel-collector.example.com"
  }'
```

**4. Deploy with ECS (Container Orchestration)**

```bash
# Update ECS task definition with new image
aws ecs update-service \
  --cluster bomipay-prod \
  --service api \
  --force-new-deployment
```

**5. Run Migrations (Post-Deploy)**

```bash
# Connect to ECS task and run migrations
aws ecs execute-command \
  --cluster bomipay-prod \
  --task <task-id> \
  --container api \
  --interactive \
  --command "/bin/bash -c 'alembic upgrade heads'"
```

**6. Monitoring & Alerting**

CloudWatch Alarms:
```bash
# API error rate > 1% for 5 min
aws cloudwatch put-metric-alarm \
  --alarm-name bomipay-api-errors \
  --alarm-description "Alert if API error rate exceeds 1%" \
  --metric-name 4XXError \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold

# Database CPU > 80%
aws cloudwatch put-metric-alarm \
  --alarm-name bomipay-db-cpu \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

---

## Backup & Restore

### Automated Backups

**PostgreSQL (AWS RDS):**
```bash
# RDS handles backups automatically (configurable retention: 1-35 days)
aws rds describe-db-instances --db-instance-identifier bomipay-prod
```

**Manual Backup:**
```bash
# Dump database
pg_dump -h <rds-endpoint> -U bomipay bomipay > bomipay-backup.sql

# Restore from dump
psql -h <rds-endpoint> -U bomipay bomipay < bomipay-backup.sql
```

**Redis (ElastiCache):**
- Snapshots stored in S3 automatically (for Redis backup clusters)
- Point-in-time recovery enabled by default

### Disaster Recovery

```bash
# Restore from RDS snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier bomipay-recovered \
  --db-snapshot-identifier bomipay-prod-snapshot-2024-01-01

# Failover to read replica (for high availability)
aws rds promote-read-replica --db-instance-identifier bomipay-replica
```

---

## Performance Tuning

### Database

```sql
-- Index frequently queried columns
CREATE INDEX idx_transactions_created_at ON transactions(created_at DESC);
CREATE INDEX idx_transactions_provider_id ON transactions(provider_id);
CREATE INDEX idx_transactions_status ON transactions(status);

-- Analyze query plans
EXPLAIN ANALYZE SELECT * FROM transactions WHERE provider_id = 1;
```

### Backend

```python
# Uvicorn workers (docker-compose.yml or systemd service)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker bomipay.main:app

# Enable query result caching
REDIS_CACHE_TTL=3600  # 1 hour
```

### Frontend

```bash
# Enable static compression
npm run build  # Next.js optimizes automatically

# Cloudflare or CloudFront for CDN
```

---

## Rollback Procedures

```bash
# View deployment history
aws ecs describe-services --cluster bomipay-prod --services api

# Rollback to previous task definition
aws ecs update-service \
  --cluster bomipay-prod \
  --service api \
  --task-definition bomipay-api:123

# Rollback database migrations
alembic downgrade -1  # or to specific revision
```

---

## Monitoring Endpoints

- **API Health:** `GET /api/v1/health`
- **Metrics:** `GET /metrics` (Prometheus format)
- **Logs:** CloudWatch, ELK, or self-hosted logging

---

## Support & Troubleshooting

- **API won't start:** Check `.env` variables, database connection, Redis availability
- **Database slow:** Check indexes, run ANALYZE, check CloudWatch metrics
- **High memory usage:** Check Celery worker queue size, consider scaling horizontally
- **SSL cert issues:** Renew with `certbot renew`, check Let's Encrypt logs

Contact: devops@bomipay.com
