# Scripts

## apply-secrets.sh

Automatically creates and updates Kubernetes secrets and configmaps from the `.env` file.

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

This script is automatically executed by Tilt when you run `tilt up`. It will:
- Run on initial startup
- Re-run whenever the `.env` file changes
- Ensure secrets are applied before the auth-service starts

### Requirements

- kubectl configured and connected to your cluster
- .env file in the repository root
- Kubernetes namespace 'default' (or modify the script)


