## ACL Proxy Auth Service (Traefik ForwardAuth + FastAPI + Redis)

Minimal auth service to protect backends behind Traefik using ForwardAuth. Tokens are hashed and stored in Redis with optional TTLs and rate limiting. Includes a tiny HTML admin UI (protected via Basic Auth).

### Architecture

- Traefik (Ingress) → ForwardAuth → FastAPI auth service → backend service
- Auth flow:
  - Client sends `Authorization: Bearer <token>`
  - Traefik calls `GET /auth` on this service
  - Service checks Redis: `tokens:<token>` hash with field `hosts`
  - If requested host is in token's allowed hosts → 200 OK; else 401/403

### Repository Layout

- `auth_service/app.py` — FastAPI app (`/auth`, `/healthz`, admin UI, hashing, rate limits)
- `auth_service/templates/index.html` — simple token manager UI
- `auth_service/requirements.txt` — pinned dependencies
- `auth_service/Dockerfile` — container for auth service
- `docker-compose.yml` — local stack with Redis + auth
- `k8s/` — K8s manifests for auth service, Redis, and Traefik middleware/ingress

### Requirements

- Docker / Docker Compose
- Redis (docker-compose provides one)

### Quick Start (Local)

1) Start stack:

```bash
docker compose up --build
```

2) Open admin UI:

```
http://localhost:8000/
```

3) Create token for hosts (comma-separated), e.g. `example.com,subdomain.example.com`. You will be prompted for Basic Auth (set via env). Optionally set TTL seconds.

4) Test the auth endpoint:

```bash
curl -H "Authorization: Bearer <your_token>" \
     -H "X-Forwarded-Host: example.com" \
     http://localhost:8000/auth
```

- OK → `200 OK` with body `OK`
- Wrong/missing token → `401`
- Token without access to host → `403`

### API & UI

- `GET /auth`
  - Headers:
    - `Authorization: Bearer <token>` (required)
    - `X-Forwarded-Host: <requested-host>` (Traefik sets this; send manually for testing)
  - Responses: `200 OK`, `401`, `403`

- `GET /healthz` → `ok` when Redis is reachable

- Admin UI
  - `GET /` — list tokens and allowed hosts, email, comment, TTL
  - `POST /create_token` (form fields: `hosts`, optional `email`, `comment`, `ttl_seconds`)
  - `POST /delete_token` (form field `token`)

### Security & Data Model

- Stored as `SHA-256(token + PEPPER)`. Raw tokens are never persisted.
- Key: `tokens:<sha256>` (hash)
  - Field: `hosts` → `host1,host2,...`
  - Optional TTL is applied per-token.
- Rate limiting: sliding buckets per token hash (`RATE_LIMIT_WINDOW_SEC`, `RATE_LIMIT_MAX`).

### Environment Variables

- `REDIS_HOST` (default: `localhost`)
- `REDIS_PORT` (default: `6379`)
- `REDIS_DB` (default: `0`)
- `REDIS_USERNAME` (optional)
- `REDIS_PASSWORD` (optional; required if Redis secured)
- `REDIS_TLS` (`true|false`, default `false`)
- `REDIS_TLS_SKIP_VERIFY` (`true|false`, default `false`)
- `PEPPER` (required; server-side secret for hashing)
- `ADMIN_USER`, `ADMIN_PASS` (required for admin UI Basic Auth)
- `TOKEN_TTL_SECONDS` (default `0`, no default TTL)
- `RATE_LIMIT_WINDOW_SEC` (default `1`)
- `RATE_LIMIT_MAX` (default `100`)

### Docker Image

Build manually (if needed):

```bash
docker build -t acl-auth-service:local ./auth_service
```

Run manually:

```bash
docker run --rm -p 8000:8000 \
  -e REDIS_HOST=host.docker.internal \
  acl-auth-service:local
```

### Kubernetes (k3s) Deployment

1) Push your image to a registry. Update `k8s/auth-service.yaml` with the image:

```yaml
containers:
  - name: auth-service
    image: ghcr.io/your-org/acl-auth-service:latest
```

2) Create secrets and configmap:

```bash
# ConfigMap
kubectl create configmap auth-service-config \
  --from-env-file=.env \
  -n default \
  --dry-run=client -o yaml | kubectl apply -f -

# App secrets
kubectl create secret generic auth-service-secrets \
  --from-literal=pepper=CHANGE_ME \
  --from-literal=admin_user=admin \
  --from-literal=admin_pass=CHANGE_ME \
  -n default --dry-run=client -o yaml | kubectl apply -f -

# Redis password
kubectl create secret generic redis-auth \
  --from-literal=password=CHANGE_ME_REDIS \
  -n default --dry-run=client -o yaml | kubectl apply -f -
```

3) Deploy:

```bash
kubectl apply -f k8s/auth-service.yaml
kubectl apply -f k8s/traefik-middleware.yaml
kubectl apply -f k8s/ingress-traefik.yaml
kubectl rollout restart deploy/auth-service -n default
```

The middleware forwards auth checks to `http://auth-service.default.svc.cluster.local:8000/auth`. Add the middleware annotation to any Ingress you want protected.

### Traefik Middleware & Ingress (example)

`k8s/ingress-traefik.yaml` defines:

- Middleware:

```yaml
apiVersion: traefik.containo.us/v1alpha1
kind: Middleware
metadata:
  name: auth-middleware
  namespace: default
spec:
  forwardAuth:
    address: "http://auth-service.default.svc.cluster.local:8000/auth"
    trustForwardHeader: true
```

- Ingress (example backend service `firecrawl-service`):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: firecrawl
  namespace: default
  annotations:
    kubernetes.io/ingress.class: traefik
    traefik.ingress.kubernetes.io/router.middlewares: default-auth-middleware@kubernetescrd
spec:
  rules:
    - host: firecrawl.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: firecrawl-service
                port:
                  number: 80
```

### Security Notes

- Use HTTPS (Traefik TLS) to encrypt tokens in transit.
- Tokens are hashed with `PEPPER` and never stored raw. Rotate `PEPPER` by re-issuing tokens.
- Use Redis AOF for persistence; back up AOF/RDB off-cluster.
- Consider managed Redis (Sentinel/Cluster) for HA; test restoration regularly.
- Restrict admin UI further with IP allowlists, NetworkPolicies, or mTLS.

### Troubleshooting

- `401 missing bearer token` — ensure `Authorization: Bearer <token>` is present.
- `401 invalid token` — token not found in Redis; create via UI.
- `403 forbidden for host` — host not in token's `hosts` list.
- `503 redis unavailable` — check Redis connection/env vars.

### License

MIT
