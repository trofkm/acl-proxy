# ACL Proxy test bench

Runs Redis, Auth Service, Traefik (ForwardAuth), and a whoami backend.

## Start

```bash
docker compose -f example/docker-compose.yml up --build
```

## Ports

| Port | Purpose |
|------|---------|
| 8000 | Auth service admin UI |
| 8080 | Traefik entrypoint |
| 8081 | Traefik dashboard |

## Test Flow

### 1. Create a token

Open http://localhost:8000, log in with `admin / admin`.

Enter `whoami.localhost` in **Hosts**, click **Create Token**.

Copy the `token` value from the response.

### 2. Request without token → 401

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: whoami.localhost" \
  http://localhost:8080/
```

### 3. Request with token → 200

```bash
curl -H "Host: whoami.localhost" \
  -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8080/
```

Returns whoami output: IP, headers, `X-Forwarded-Host`.

### 4. Token for a different host → 403

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: evil.localhost" \
  -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8080/
```

### 5. Rate limit → 429

```bash
for i in $(seq 1 110); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Host: whoami.localhost" \
    -H "Authorization: Bearer <TOKEN>" \
    http://localhost:8080/
done
```

First 100 requests → `200`, then `429`.

## Stop

```bash
docker compose -f example/docker-compose.yml down -v
```
