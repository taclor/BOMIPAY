# Bomi Pay — AI-Driven Payment Intelligence Operating System

Nigerian payment intelligence platform for reconciliation, provider management, and financial insights.

**Features:** Transaction reconciliation • Provider health monitoring • Payment graph visualization • Incident management • AI operations assistant

## Quick Start

### Development Setup

**1. Clone & Install Backend**
```bash
cd d:\DEV_CONTAINERS\BOMIPAY  # or wherever cloned
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e .  # Install from pyproject.toml
```

**2. Install Frontend**
```bash
cd bomipay-website
npm install
```

**3. Start Services (Docker)**
```bash
# In repo root
docker-compose up -d
```

**4. Run Database Migrations**
```bash
python -m alembic upgrade heads
```

**5. Start Backend Server (Terminal 1)**
```bash
python -m uvicorn bomipay.main:app --reload
```

**6. Start Frontend Server (Terminal 2)**
```bash
cd bomipay-website
npm run dev
```

### Access URLs
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/api/v1 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |

### Demo Login
- **Email:** admin@bomipay.com
- **Password:** Admin1234!Demo

### Docker Production Build
```bash
docker-compose -f docker-compose.prod.yml up -d
python -m alembic upgrade heads
```

## Architecture

- **Backend:** FastAPI (Python 3.11+) with SQLAlchemy 2.0 async ORM
- **Frontend:** Next.js 14 with React 19, Tailwind CSS, TypeScript
- **Database:** PostgreSQL 16
- **Cache/Queue:** Redis 8 + Celery async jobs
- **Monitoring:** OpenTelemetry, Prometheus, optional Sentry
- **Security:** JWT auth, bcrypt passwords, encrypted provider keys

## Development

### Testing
```bash
# Backend
pytest tests/ -v

# Frontend
cd bomipay-website && npm run build
```

### Linting
```bash
# Frontend
cd bomipay-website && npm run lint
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "describe change"

# Apply migrations
alembic upgrade heads

# Rollback
alembic downgrade -1
```

## Project Structure

```
bomipay/
├── src/bomipay/           # Backend application
│   ├── main.py            # FastAPI app initialization
│   ├── api/               # Route handlers
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic request/response schemas
│   ├── services/          # Business logic
│   └── core/              # Config, auth, dependencies
├── bomipay-website/       # Next.js frontend
│   ├── src/app/           # Route pages
│   ├── src/lib/           # Utilities, API client
│   └── src/components/    # React components
├── alembic/               # Database migrations
├── tests/                 # Backend pytest tests
├── docker-compose.yml     # Local development services
├── docker-compose.prod.yml # Production deployment
└── pyproject.toml         # Backend dependencies
```

## Deployment

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for:
- Staging deployment
- Production deployment  
- SSL/TLS setup
- Environment configuration
- Backup & restore procedures
- Monitoring & health checks

## Configuration

Backend configuration via environment variables (see [.env.example](.env.example)):
```bash
SECRET_KEY              # Min 32 random chars
BOMIPAY_ENV             # development/staging/production
DATABASE_URL            # PostgreSQL async connection
REDIS_URL               # Redis connection
CORS_ALLOWED_ORIGINS    # Comma-separated allowed origins
JWT_ACCESS_TOKEN_EXPIRE_SECONDS    # Default: 900 (15 min)
JWT_REFRESH_TOKEN_EXPIRE_SECONDS   # Default: 604800 (7 days)
```

Frontend configuration via [bomipay-website/.env.local]:
```bash
NEXT_PUBLIC_API_URL     # Backend API base URL
```

## Team

**Product:** Nigerian fintech payment intelligence  
**Stack:** FastAPI + Next.js + PostgreSQL + Redis + Celery  
**License:** Proprietary
