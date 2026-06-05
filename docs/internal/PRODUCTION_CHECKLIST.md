# Bomi Pay Production Readiness Checklist

## Infrastructure
- [ ] PostgreSQL running with persistent volume
- [ ] Redis running
- [ ] Nginx configured with SSL
- [ ] Celery worker running
- [ ] Celery beat running

## Application
- [ ] SECRET_KEY set (min 32 chars, random)
- [ ] DATABASE_URL points to PostgreSQL (not SQLite)
- [ ] REDIS_URL configured
- [ ] CORS_ALLOWED_ORIGINS set to production domain
- [ ] BOMIPAY_ENV=production
- [ ] Alembic migrations applied: `alembic upgrade heads`
- [ ] Sentry DSN configured (optional)

## Security
- [ ] No debug mode
- [ ] No SQLite in production
- [ ] Secrets not in version control
- [ ] HTTPS enforced
- [ ] DOCS_ENABLED=false (disable Swagger UI in production)

## Operations
- [ ] Health check endpoint responding: GET /api/v1/health
- [ ] Readiness probe responding: GET /api/v1/health/ready
- [ ] Logs structured (JSON)
- [ ] Backup script configured
- [ ] Monitoring/alerting configured
