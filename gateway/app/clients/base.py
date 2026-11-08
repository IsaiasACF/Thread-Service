from typing import Any

import httpx

from ..graphql.errors import ErrorCode, GatewayError


class RestClient:
    """Shared transport only. Subclasses own REST paths, DTOs and validation."""
    service: str

    def __init__(self, http: httpx.AsyncClient, base_url: str | None):
        self.http = http
        self.base_url = base_url

    async def request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.base_url:
            raise GatewayError("Servicio no configurado.", ErrorCode.UPSTREAM_UNAVAILABLE,
                               service=self.service)
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise ValueError("REST paths must be relative to the configured service")
        try:
            response = await self.http.request(
                method, self.base_url.rstrip("/") + path,
                follow_redirects=False, **kwargs)
        except httpx.TimeoutException:
            raise GatewayError("El servicio excedió el tiempo de espera.",
                               ErrorCode.UPSTREAM_TIMEOUT, service=self.service) from None
        except httpx.RequestError:
            raise GatewayError("Servicio no disponible.", ErrorCode.UPSTREAM_UNAVAILABLE,
                               service=self.service) from None
        if not 200 <= response.status_code < 300:
            code = {400: ErrorCode.VALIDATION_ERROR, 422: ErrorCode.VALIDATION_ERROR,
                    404: ErrorCode.NOT_FOUND, 403: ErrorCode.FORBIDDEN,
                    409: ErrorCode.CONFLICT, 410: ErrorCode.GONE,
                    503: ErrorCode.UPSTREAM_UNAVAILABLE, 504: ErrorCode.UPSTREAM_TIMEOUT
                    }.get(response.status_code, ErrorCode.BAD_UPSTREAM_RESPONSE)
            raise GatewayError("El servicio no pudo completar la solicitud.", code,
                               service=self.service, http_status=response.status_code)
        try:
            return response.json()
        except ValueError:
            raise self.bad_response() from None

    def bad_response(self) -> GatewayError:
        return GatewayError("Respuesta incompatible del servicio.",
                            ErrorCode.BAD_UPSTREAM_RESPONSE, service=self.service)
