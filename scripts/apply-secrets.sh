#!/bin/bash
set -e

# Create K8s secrets and configmaps from .env

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    echo "Please copy env.example to .env and configure your secrets"
    exit 1
fi

echo "Loading environment variables from $ENV_FILE"
source "$ENV_FILE"

echo "Creating Kubernetes secrets and configmaps..."

# ConfigMap
echo "→ Creating auth-service-config ConfigMap..."
kubectl create configmap auth-service-config \
  --from-literal=TOKEN_TTL_SECONDS="${TOKEN_TTL_SECONDS:-36000000}" \
  --from-literal=RATE_LIMIT_WINDOW_SEC="${RATE_LIMIT_WINDOW_SEC:-1}" \
  --from-literal=RATE_LIMIT_MAX="${RATE_LIMIT_MAX:-20}" \
  -n default \
  --dry-run=client -o yaml | kubectl apply -f -

# Create auth-service secrets
echo "→ Creating auth-service-secrets Secret..."
kubectl create secret generic auth-service-secrets \
  --from-literal=pepper="${PEPPER:-change-me-pepper}" \
  --from-literal=admin_user="${ADMIN_USER:-admin}" \
  --from-literal=admin_pass="${ADMIN_PASS:-admin}" \
  -n default \
  --dry-run=client -o yaml | kubectl apply -f -

# Create Redis secret
echo "→ Creating redis-auth Secret..."
kubectl create secret generic redis-auth \
  --from-literal=password="${REDIS_PASSWORD:-admin}" \
  -n default \
  --dry-run=client -o yaml | kubectl apply -f -

echo "✓ Successfully created/updated all secrets and configmaps"
