#!/bin/bash
# Startup script for BomiPay application
# Runs migrations and starts the application
# Usage: ./scripts/startup.sh or as Docker CMD

set -e

echo "[$(date)] Starting BomiPay initialization..."

# Check required environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable not set"
    exit 1
fi

if [ -z "$REDIS_URL" ]; then
    echo "ERROR: REDIS_URL environment variable not set"
    exit 1
fi

# Wait for database to be ready
echo "[$(date)] Waiting for database to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if python -c "from sqlalchemy import create_engine, text; engine = create_engine('$DATABASE_URL'); engine.execute(text('SELECT 1')); print('Database is ready')" 2>/dev/null; then
        echo "[$(date)] Database is ready!"
        break
    fi
    attempt=$((attempt + 1))
    echo "[$(date)] Database not ready yet... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Database did not become ready after $((max_attempts * 2)) seconds"
    exit 1
fi

# Wait for Redis to be ready
echo "[$(date)] Waiting for Redis to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if python -c "import redis; r = redis.from_url('$REDIS_URL'); r.ping(); print('Redis is ready')" 2>/dev/null; then
        echo "[$(date)] Redis is ready!"
        break
    fi
    attempt=$((attempt + 1))
    echo "[$(date)] Redis not ready yet... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Redis did not become ready after $((max_attempts * 2)) seconds"
    exit 1
fi

# Run database migrations
echo "[$(date)] Running database migrations..."
if python -m alembic upgrade heads; then
    echo "[$(date)] Migrations completed successfully!"
else
    echo "ERROR: Database migration failed"
    exit 1
fi

# Check migration status
current_migration=$(python -m alembic current)
echo "[$(date)] Current migration: $current_migration"

# Start the application
echo "[$(date)] Starting BomiPay application..."
exec "$@"
