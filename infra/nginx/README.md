# Edge nginx

`edge.conf` terminates TLS, enforces security headers + rate limits, and
reverse-proxies to the backend (`/api`, `/ws`) and the static SPA (`/`).

## Certificates

Mount a directory containing `fullchain.pem` and `privkey.pem` into
`/etc/nginx/ssl`. Override the host path with the `TLS_CERT_DIR` env var.

### Production (Let's Encrypt)

```
docker run --rm -v $(pwd)/infra/nginx/ssl:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  -d geosentinel.example.com \
  -m ops@geosentinel.example.com --agree-tos
# Then symlink/copy live/<domain>/{fullchain,privkey}.pem into the mount.
```

Schedule renewals via cron or a certbot sidecar.

### Smoke tests (self-signed)

```
mkdir -p infra/nginx/ssl
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout infra/nginx/ssl/privkey.pem \
  -out     infra/nginx/ssl/fullchain.pem \
  -days 90 -subj '/CN=localhost'
```

## Security headers

The vhost sets HSTS, X-Frame-Options, X-Content-Type-Options,
Referrer-Policy, Permissions-Policy, and a strict CSP. When swapping
basemap providers or adding a third-party script host, update the CSP
`script-src` / `img-src` / `connect-src` lists.

## Rate limits

- `/api/v1/auth/login` — 5 req/min per IP, burst 3.
- `/api/v1/sensors/ingest` — 30 req/s keyed by `X-Gateway-API-Key`, burst 60.
- `/ws/` — 20 concurrent connections per IP.

All breaches return HTTP 429 with an `X-RateLimit-*` hint.
