# Benchmark Catalog API

Base URL during the manual run: `http://127.0.0.1:8765`.

## Health

`GET /health` requires no authentication and returns JSON containing
`status=ok`.

## Catalog v1

`GET /v1/catalog` accepts optional query parameter `cursor`. Send the token from
`CATALOG_TOKEN` as `X-Client-Token`. A successful v1 response has:

```json
{
  "items": [
    {"id": "p1", "name": "Alpha", "price_cents": 100, "version": 1}
  ],
  "next_cursor": "opaque-token-or-null"
}
```

The service may return `429` or `503`. `429` can include `Retry-After` in
seconds. Cursors are opaque and must not be constructed by the client.

The running service is the authority. This document does not authorize reading
the benchmark server implementation.
