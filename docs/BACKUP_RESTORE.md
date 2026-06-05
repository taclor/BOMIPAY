# BomiPay Backup & Restore Procedures

## Overview

This document describes backup, restore, and disaster recovery procedures for BomiPay.

- **Recovery Time Objective (RTO):** 4 hours
- **Recovery Point Objective (RPO):** 24 hours (daily backups)
- **Last Backup:** [TBD - update after first production backup]
- **Last Restore Test:** [TBD - update after first restore test]

---

## Automated Backup Schedule

### PostgreSQL Database

**Local Development / Docker:**
```bash
# Manual backup using backup.sh script
./scripts/backup.sh
```

**Production (AWS RDS):**
- Automated daily backups enabled
- Retention: 30 days (configurable)
- Multi-AZ automatic failover enabled
- Point-in-time recovery: enabled
- Backup window: 03:00-04:00 UTC (configurable)

**Staging:**
- Automated daily backups enabled
- Retention: 14 days
- Backup window: 02:00-03:00 UTC

### Redis Cache

**Local Development / Docker:**
- Persistence enabled with AOF (Append Only File)
- Snapshot saved every 15 minutes
- Data persisted to volume `redis_data:/data`

**Production (AWS ElastiCache):**
- Automatic snapshots enabled
- Snapshot retention: 14 days
- Daily snapshot at 04:30 UTC
- Data saved to S3 automatically

**Staging:**
- Automatic snapshots enabled
- Snapshot retention: 7 days

### Application Files

**Local Development:**
```bash
# Backup uploaded files (if using local storage)
tar -czf backups/files_$(date +%Y%m%d_%H%M%S).tar.gz \
  src/bomipay/data/uploads/
```

**Production:**
- S3 automatically versions all uploaded files
- Versioning enabled: retention 90 days
- Backup copies to secondary region: daily

---

## Manual Backup Procedures

### PostgreSQL Full Backup (Docker)

```bash
# From repository root
./scripts/backup.sh

# Output:
# [2024-01-15 14:30:45] Starting database backup to ./backups/bomipay_20240115_143045.sql.gz...
# [2024-01-15 14:30:47] Backup complete: ./backups/bomipay_20240115_143045.sql.gz
# -rw-r--r-- 1 user user 2.4M Jan 15 14:30 ./backups/bomipay_20240115_143045.sql.gz
```

**Environment Variables:**
```bash
# Optional: customize backup behavior
export BACKUP_DIR=./backups  # default
export RETENTION_DAYS=30     # default
```

### PostgreSQL Full Backup (AWS RDS)

```bash
# Using AWS CLI to create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier bomipay-prod \
  --db-snapshot-identifier bomipay-prod-manual-$(date +%Y%m%d-%H%M%S)

# List all snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier bomipay-prod \
  --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime,AllocatedStorage]' \
  --output table

# Download backup for offline storage
pg_dump \
  --host=<rds-endpoint> \
  --username=bomipay \
  --format=custom \
  --verbose \
  bomipay_prod > bomipay_backup_$(date +%Y%m%d_%H%M%S).dump
```

### Redis Snapshot (Docker)

```bash
# Inside Redis container
docker exec bomipay-redis redis-cli BGSAVE

# Output: Background saving started
# Snapshot file: bomipay_data-volume:/data/dump.rdb

# To copy locally:
docker cp bomipay-redis:/data/dump.rdb ./backups/redis_$(date +%Y%m%d_%H%M%S).rdb
```

### Redis Snapshot (AWS ElastiCache)

```bash
# Create automatic backup (automatic daily)
# Or create manual backup via AWS Console

# Download via S3
aws s3 ls s3://my-backup-bucket/redis-backups/
aws s3 cp s3://my-backup-bucket/redis-backups/redis_backup.rdb ./backups/
```

---

## Restore Procedures

### ⚠️ Pre-Restore Warning

**CRITICAL:** Restoring from backup will:
- Overwrite current database
- Delete transactions created after backup timestamp
- Require application restart
- Require DNS/routing update (if changing database host)

**Always:**
1. ✅ Test restore procedure in staging first
2. ✅ Notify all users of maintenance window
3. ✅ Stop accepting new transactions (graceful shutdown)
4. ✅ Verify backup integrity before restore
5. ✅ Have rollback plan ready

---

### PostgreSQL Restore (Docker)

```bash
# 1. Identify backup file
ls -lh ./backups/bomipay_*.sql.gz

# 2. Run restore script (with 10-second abort window)
./scripts/restore.sh ./backups/bomipay_20240115_143045.sql.gz

# Output:
# [2024-01-15 15:00:00] Starting restore from ./backups/bomipay_20240115_143045.sql.gz...
# [2024-01-15 15:00:00] WARNING: This will overwrite the current database!
# [2024-01-15 15:00:00] Press Ctrl+C to abort (will timeout in 10 seconds)...
# [2024-01-15 15:00:10] Restoring from backup... (may take several minutes)
# [2024-01-15 15:02:30] Restore complete from ./backups/bomipay_20240115_143045.sql.gz
# [2024-01-15 15:02:30] Restore script finished successfully

# 3. Verify restore
docker-compose exec db psql -U bomipay -d bomipay -c \
  "SELECT COUNT(*) as transaction_count FROM transactions;"

# 4. Check data integrity
docker-compose exec api python -m alembic current
```

**For specific table restore:**
```bash
# Restore only transactions table
gunzip -c ./backups/bomipay_backup.sql.gz | \
  psql -h localhost -U bomipay -d bomipay -c \
  "BEGIN; DELETE FROM transactions; COMMIT;" && \
  psql -h localhost -U bomipay -d bomipay < transactions.sql
```

### PostgreSQL Restore (AWS RDS)

```bash
# 1. Restore from snapshot (creates new DB instance)
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier bomipay-prod-restored \
  --db-snapshot-identifier bomipay-prod-snapshot-20240115

# 2. Wait for restore to complete (typically 10-30 min)
aws rds describe-db-instances \
  --db-instance-identifier bomipay-prod-restored \
  --query 'DBInstances[0].[DBInstanceStatus,LatestRestorableTime]'

# Expected: DBInstanceStatus: available

# 3. Update application DATABASE_URL to point to new instance
# (or CNAME alias if using Route 53)

# 4. Run migrations if needed
# (usually not needed if backup includes schema)

# 5. Verify data integrity
psql -h bomipay-prod-restored.c.amazonaws.com -U bomipay -d bomipay -c \
  "SELECT COUNT(*) as transaction_count FROM transactions; \
   SELECT COUNT(*) as settlement_count FROM settlements;"

# 6. Swap DNS/CNAME to point to restored instance
# aws route53 change-resource-record-sets ...

# 7. Monitor application logs for errors
# aws logs tail /aws/ecs/bomipay-prod --follow

# 8. Once verified, delete old instance
aws rds delete-db-instance \
  --db-instance-identifier bomipay-prod \
  --skip-final-snapshot
```

### Redis Restore (Docker)

```bash
# 1. Stop Redis to prevent data overwrites
docker-compose stop redis

# 2. Restore dump.rdb file
docker cp ./backups/redis_20240115_143045.rdb bomipay-redis:/data/dump.rdb

# 3. Restart Redis (loads dump.rdb automatically)
docker-compose up -d redis

# 4. Verify data
docker-compose exec redis redis-cli DBSIZE
docker-compose exec redis redis-cli KEYS "*"
```

### Redis Restore (AWS ElastiCache)

```bash
# 1. Create new cluster from backup
aws elasticache create-cache-cluster \
  --cache-cluster-id bomipay-prod-restored \
  --snapshot-name bomipay-prod-snapshot-20240115

# 2. Wait for cluster to be available
aws elasticache describe-cache-clusters \
  --cache-cluster-id bomipay-prod-restored \
  --query 'CacheClusters[0].[CacheClusterStatus,CacheNodes[0].Endpoint.Address]'

# 3. Update application REDIS_URL
# (or use ElastiCache replication group for automatic failover)

# 4. Restart application
aws ecs update-service --cluster bomipay-prod --service api --force-new-deployment

# 5. Monitor metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ElastiCache \
  --metric-name CPUUtilization \
  --dimensions Name=CacheClusterId,Value=bomipay-prod-restored \
  --start-time 2024-01-15T14:00:00Z \
  --end-time 2024-01-15T16:00:00Z \
  --period 300 --statistics Average
```

---

## Verification Procedures

### Backup Integrity Check

```bash
# Verify backup file is valid SQL
gunzip -t ./backups/bomipay_20240115_143045.sql.gz

# Count records in backup (without restoring)
gunzip -c ./backups/bomipay_20240115_143045.sql.gz | \
  grep "^COPY transactions" -A 1000000 | \
  wc -l

# Expected: Should show reasonable transaction count (e.g., > 100)
```

### Post-Restore Validation

```bash
# 1. Check database connections
docker-compose exec api python -c \
  "from bomipay.db import engine; print(engine)"

# 2. Verify table counts
docker-compose exec db psql -U bomipay -d bomipay -c \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' \
   ORDER BY tablename;" | wc -l

# Expected: Should match pre-backup table count

# 3. Check for data corruption
docker-compose exec db psql -U bomipay -d bomipay -c \
  "SELECT * FROM pg_stat_user_tables \
   WHERE n_live_tup = 0 AND n_dead_tup > 0;" | head -10

# Expected: No tables with dead tuples (indicates corruption)

# 4. Run application health check
curl http://localhost:8082/api/v1/health/ready
# Expected: {"status":"ready","db":"ok","redis":"ok"}
```

---

## Disaster Recovery Plan

### Complete Infrastructure Failure (Data Loss)

**Scenario:** Entire production database and Redis lost; need to recover from backups.

**Steps:**

1. **Assess damage** (5 min)
   ```bash
   aws rds describe-db-instances --db-instance-identifier bomipay-prod
   aws elasticache describe-cache-clusters --cache-cluster-id bomipay-prod
   # If both show "deleting" or "failed" → full disaster recovery needed
   ```

2. **Provision new infrastructure** (20-30 min)
   - Create new RDS instance from latest snapshot
   - Create new ElastiCache cluster from latest snapshot
   - Verify security groups and network access

3. **Update application configuration** (5 min)
   - Update DATABASE_URL in AWS Secrets Manager
   - Update REDIS_URL in AWS Secrets Manager
   - Trigger application redeploy

4. **Run migrations** (2-5 min)
   - Connect to ECS task and run `alembic upgrade heads`
   - Verify schema matches expected version

5. **Validate data** (10 min)
   - Check transaction counts
   - Verify settlement records
   - Test critical APIs

6. **User notification** (ongoing)
   - Update status page: "Infrastructure recovered, testing in progress"
   - Notify support team of data loss window (backup timestamp to recovery time)
   - Prepare communication for affected users

**Expected Recovery Time: 45-60 minutes**

### Database Corruption

**Scenario:** Database becomes corrupted; need to recover to last known good state.

1. **Create manual snapshot immediately** (1 min)
   ```bash
   aws rds create-db-snapshot \
     --db-instance-identifier bomipay-prod \
     --db-snapshot-identifier bomipay-prod-corrupted-$(date +%s)
   ```

2. **Restore from previous snapshot** (20 min)
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier bomipay-prod-recovered \
     --db-snapshot-identifier bomipay-prod-snapshot-20240114
   ```

3. **Run VACUUM ANALYZE** (10 min)
   ```bash
   psql -h new-rds-endpoint.amazonaws.com -U bomipay -d bomipay -c "VACUUM ANALYZE;"
   ```

4. **Swap DNS** (5 min)
   - Update Route 53 or application config to point to recovered DB

**Expected Recovery Time: 35-40 minutes**

---

## Backup Retention Policy

| Backup Type | Environment | Retention | Frequency |
|-------------|-------------|-----------|-----------|
| PostgreSQL | Production | 30 days | Daily |
| PostgreSQL | Staging | 14 days | Daily |
| PostgreSQL | Dev | 7 days | Manual |
| Redis | Production | 14 days | Daily |
| Redis | Staging | 7 days | Daily |
| Application Files (S3) | Production | 90 days | Continuous versioning |

---

## Backup Storage Locations

| Type | Environment | Primary | Secondary Backup |
|------|-------------|---------|-----------------|
| PostgreSQL | Production | AWS RDS (automated) | S3 (automated export daily) |
| PostgreSQL | Staging | RDS (automated) | Local backups (manual) |
| Redis | Production | ElastiCache snapshots | S3 (automated export) |
| Application Code | Production | GitHub (versioned) | S3 bucket (sync weekly) |

---

## Testing Backup & Restore

### Quarterly Restore Test (Recommended)

```bash
# Q1: Test PostgreSQL restore
# 1. Select oldest backup
# 2. Spin up test environment with backup
# 3. Run full test suite
# 4. Document issues and update procedures

# Q2: Test Redis restore
# 1. Test ElastiCache restore procedure
# 2. Verify data consistency

# Q3: Test full disaster recovery
# 1. Simulate complete infrastructure failure
# 2. Execute full recovery playbook
# 3. Document recovery time and issues

# Q4: Test application migration to new infrastructure
```

### Last Restore Test: [TBD - update after first test]

**Test Date:** [Date]  
**Backup Used:** [Backup ID]  
**Issues Found:** [Issues, if any]  
**Recovery Time:** [Minutes]  
**Status:** ✅ PASSED / ⚠️ ISSUES / ❌ FAILED  

---

## Emergency Contacts

- **DevOps Lead:** [Name] - [Email/Phone]
- **Database Administrator:** [Name] - [Email/Phone]
- **AWS Account Manager:** [Name] - [Email/Phone]
- **Incident Commander:** [Name] - [Email/Phone]

---

## Related Documentation

- [Deployment Guide](./DEPLOYMENT.md) - Full deployment procedures
- [Runbook](./RUNBOOK.md) - Operational procedures
- [Incident Response](./INCIDENT_RESPONSE.md) - Crisis management
- [AWS Console](https://console.aws.amazon.com) - Infrastructure management

---

**Last Updated:** 2024-01-15  
**Next Review:** 2024-04-15
