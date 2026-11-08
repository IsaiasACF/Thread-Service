from enum import StrEnum

from graphql import GraphQLError


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    GONE = "GONE"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    BAD_UPSTREAM_RESPONSE = "BAD_UPSTREAM_RESPONSE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class GatewayError(GraphQLError):
    def __init__(self, message: str, code: ErrorCode, *, service: str | None = None,
                 http_status: int | None = None):
        extensions = {"code": code.value}
        if service is not None:
            extensions["service"] = service
        if http_status is not None:
            extensions["httpStatus"] = http_status
        super().__init__(message, extensions=extensions)


def format_error(error: GraphQLError, debug: bool = False) -> dict:
    # Never publish arbitrary exception messages, extensions or debug context.
    original = error.original_error
    if isinstance(original, GatewayError) or isinstance(error, GatewayError):
        public = original if isinstance(original, GatewayError) else error
        result = {"message": public.message, "extensions": public.extensions}
    elif original is None:
        result = {"message": "Consulta GraphQL inválida.",
                  "extensions": {"code": ErrorCode.VALIDATION_ERROR.value}}
    else:
        result = {"message": "Error interno del Gateway.",
                  "extensions": {"code": ErrorCode.INTERNAL_ERROR.value}}
    if error.locations:
        result["locations"] = [location.formatted for location in error.locations]
    if error.path:
        result["path"] = error.path
    return result


def pending(service: str):
    def resolver(*_, **__):
        raise GatewayError("Funcionalidad pendiente de implementación.",
                           ErrorCode.NOT_IMPLEMENTED, service=service)
    return resolver
