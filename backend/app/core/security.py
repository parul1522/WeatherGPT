"""Request authentication helpers.

For the prototype, access is protected by an optional shared API key (X-API-Key header).
When JWT auth is added later, replace `verify_api_key` with a dependency that decodes the
token and returns the user; routers already attach this dependency in one place (main.py).
"""

import secrets
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    api_key: Annotated[str | None, Security(api_key_header)] = None,
) -> None:
    expected = settings.API_KEY
    if expected is None:
        return
    # compare_digest avoids leaking the key through response timing.
    if not api_key or not secrets.compare_digest(api_key, expected.get_secret_value()):
        raise AuthenticationError()


def describe_secret(value: SecretStr | None) -> str:
    """Safe description of a secret for logs: never prints the value itself."""
    if value is None:
        return "not set"
    raw = value.get_secret_value()
    return f"set (…{raw[-4:]})" if len(raw) >= 12 else "set"
