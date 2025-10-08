## ACL Proxy Auth Service (Traefik ForwardAuth + FastAPI + Redis)

Minimal auth service to protect backends behind Traefik using ForwardAuth. Tokens are stored in Redis and are allowed for a comma-separated list of hosts. Includes a tiny HTML admin UI.

### Architecture

- Traefik (Ingress) → ForwardAuth → FastAPI auth service → backend service
- Auth flow:
  - Client sends `Authorization: Bearer <token>`
  - Traefik calls `GET /auth` on this service
  - Service checks Redis: `tokens:<token>` hash with field `hosts`
  - If requested host is in token's allowed hosts → 200 OK; else 401/403

### Repository Layout

- `auth_service/app.py` — FastAPI app (`/auth`, `/healthz`, admin UI)
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

3) Create token for hosts (comma-separated), e.g. `trofkm.ru,firecrawl.trofkm.ru`.

4) Test the auth endpoint:

```bash
curl -H "Authorization: Bearer <your_token>" \
     -H "X-Forwarded-Host: trofkm.ru" \
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
  - `GET /` — list tokens and allowed hosts
  - `POST /create_token` (form field `hosts`)
  - `POST /delete_token` (form field `token`)

### Redis Data Model

- Key: `tokens:<token>` (hash)
  - Field: `hosts` → `host1,host2,...`

### Environment Variables

- `REDIS_HOST` (default: `localhost`)
- `REDIS_PORT` (default: `6379`)
- `REDIS_DB` (default: `0`)

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

1) Push your built image to a registry and update image in `k8s/auth-service.yaml`:

```yaml
containers:
  - name: auth-service
    image: ghcr.io/your-org/acl-auth-service:latest
```

2) Apply manifests:

```bash
kubectl apply -f k8s/auth-service.yaml
kubectl apply -f k8s/ingress-traefik.yaml
```

Notes:
- The Traefik middleware in `k8s/ingress-traefik.yaml` forwards to `http://auth-service.default.svc.cluster.local:8000/auth`.
- Add the middleware annotation to any Ingress you want protected.

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
    - host: firecrawl.trofkm.ru
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

- Use HTTPS on the public edge (Traefik TLS) so tokens are not sent in cleartext.
- Consider rotating tokens regularly and minimizing allowed hosts per token.
- Restrict access to the admin UI (e.g., network policies, basic auth, or mTLS in cluster).

### Troubleshooting

- `401 missing bearer token` — ensure `Authorization: Bearer <token>` is present.
- `401 invalid token` — token not found in Redis; create via UI.
- `403 forbidden for host` — host not in token's `hosts` list.
- `503 redis unavailable` — check Redis connection/env vars.

### License

MIT


