import secrets

from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    configured_key = settings.api_access_token
    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="Acesso à API não configurado pelo operador.",
        )
    if x_api_key is None or not secrets.compare_digest(x_api_key, configured_key):
        raise HTTPException(
            status_code=401,
            detail="Credencial de API ausente ou inválida.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
