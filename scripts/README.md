# Scripts

## apply-secrets.sh

Creates and updates Kubernetes secrets and configmaps from `.env`.

### Usage

```bash
# Make sure you have a .env file in the repo root
cp ../env.example ../.env
# Edit .env with your actual values

# Run the script manually
./apply-secrets.sh
```

### What it creates

1. **ConfigMap: auth-service-config**
   - TOKEN_TTL_SECONDS
   - RATE_LIMIT_WINDOW_SEC
   - RATE_LIMIT_MAX

2. **Secret: auth-service-secrets**
   - pepper (encryption pepper)
   - admin_user (basic auth username)
   - admin_pass (basic auth password)

3. **Secret: redis-auth**
   - password (Redis password)

### Integration with Tilt

Tilt runs this script when you `tilt up`:
- On first startup
- When `.env` changes
- Before auth-service deploys (secrets must exist first)

### Requirements

- kubectl configured and connected to your cluster
- .env file in the repository root
- Kubernetes namespace 'default' (or modify the script)


