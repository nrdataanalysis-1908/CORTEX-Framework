# API security baseline

## API key authentication

The `POST /documents`, `POST /ask`, and `GET /metrics` routes require an API key in the `X-API-Key` header.

Configure `API_ACCESS_TOKEN` in the service environment with a cryptographically random secret of at least 32 characters. Do not commit the value, place it in client-side code, or expose it in logs. Use a secret manager in deployed environments and rotate the token after suspected disclosure.

Protected routes fail closed:
- Missing server configuration returns HTTP 503.
- Missing or invalid client credentials return HTTP 401 and a `WWW-Authenticate` challenge.
- Comparisons use `secrets.compare_digest`.

The liveness and readiness endpoints remain unauthenticated for platform probes. API key authentication is a single shared credential; it does not provide user identity, roles, tenant isolation, per-client revocation, or rate limiting. Deploy behind TLS and a trusted ingress. Do not expose the service directly to an untrusted network.

## Client example

```http
POST /ask
X-API-Key: <configured-secret>
Content-Type: application/json

{"question":"What is the documented response target?"}
```

## Scope

This is an initial access-control boundary for the experimental API, not a complete production identity and authorization system. Follow-up work should introduce managed identities or OAuth2/JWT, authorization scopes, per-client credentials, rate limiting, and audit trails before multi-tenant or public deployment.
