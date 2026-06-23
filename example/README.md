# Wicket test bench

This test bench runs the auth service, a reverse proxy with ForwardAuth, and a whoami backend.

Two proxy variants: **Traefik** and **Caddy**. Each supports two storage backends.

## Start

Traefik + SQLite:

```bash
docker compose -f example/traefik/docker-compose.sqlite.yml up --build
```

Traefik + Redis:

```bash
docker compose -f example/traefik/docker-compose.redis.yml up --build
```

Caddy + SQLite:

```bash
docker compose -f example/caddy/docker-compose.sqlite.yml up --build
```

Caddy + Redis:

```bash
docker compose -f example/caddy/docker-compose.redis.yml up --build
```

## Ports

| Port | Purpose |
|------|---------|
| 8000 | Auth service admin UI |
| 8080 | Proxy entrypoint |

Traefik only:

| Port | Purpose |
|------|---------|
| 8081 | Traefik dashboard |

## Test Flow

### 1. Create a token

Open http://localhost:8000, log in with `test-admin / test-admin`.

Enter `whoami.localhost` in **Hosts**, click **Create Token**.

Copy the `token` value from the response.

### 2. Request without token: 401

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: whoami.localhost" \
  http://localhost:8080/
```

### 3. Request with token: 200

```bash
curl -H "Host: whoami.localhost" \
  -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8080/
```

Returns whoami output: IP, headers, `X-Forwarded-Host`.

### 4. Token for a different host: not routed

The proxy only routes requests with `Host: whoami.localhost`. A request with a different host
does not reach the auth service.

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: evil.localhost" \
  -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8080/
```

Traefik returns `404`, Caddy returns `200` with empty body.

## Stop

```bash
docker compose -f example/traefik/docker-compose.sqlite.yml down -v
docker compose -f example/traefik/docker-compose.redis.yml down -v
docker compose -f example/caddy/docker-compose.sqlite.yml down -v
docker compose -f example/caddy/docker-compose.redis.yml down -v
```
