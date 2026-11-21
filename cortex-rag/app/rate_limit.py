import hashlib
import math

import psycopg
from fastapi import Header, HTTPException

from app.config import settings
from app.db import connect
from app.security import require_api_key


def enforce_api_rate_limit(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Authenticate the caller and enforce a shared PostgreSQL fixed-window limit."""
    require_api_key(x_api_key)
    if x_api_key is None:  # Defensive; require_api_key already rejects this case.
        raise HTTPException(status_code=401, detail="Credencial de API ausente ou inválida.")

    key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
    try:
        with connect() as conn:
            row = conn.execute(
                """
                INSERT INTO api_rate_limits (key_hash, window_start, request_count)
                VALUES (%s, date_trunc('minute', NOW()), 1)
                ON CONFLICT (key_hash) DO UPDATE
                SET
                    window_start = EXCLUDED.window_start,
                    request_count = CASE
                        WHEN api_rate_limits.window_start = EXCLUDED.window_start
                        THEN LEAST(
                            api_rate_limits.request_count + 1,
                            %s + 1
                        )
                        ELSE 1
                    END
                RETURNING
                    request_count,
                    GREATEST(
                        1,
                        CEIL(EXTRACT(EPOCH FROM (
                            date_trunc('minute', NOW()) + INTERVAL '1 minute' - NOW()
                        )))::integer
                    )
                """,
                (key_hash, settings.api_rate_limit_requests_per_minute),
            ).fetchone()
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Serviço de controle de tráfego temporariamente indisponível.",
            headers={"Retry-After": "5"},
        ) from exc

    request_count, retry_after = row
    if request_count > settings.api_rate_limit_requests_per_minute:
        raise HTTPException(
            status_code=429,
            detail="Limite de requisições por minuto excedido.",
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )
