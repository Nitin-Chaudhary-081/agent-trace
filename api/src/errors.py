"""Typed API errors and the standard error envelope.

Every error response uses: {"error": {"code", "message", ...details}}.
"""


class ApiError(Exception):
    def __init__(self, message: str, code: str, status_code: int = 500, details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(ApiError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} not found: {identifier}",
            "NOT_FOUND",
            404,
            {"resource": resource, "id": identifier},
        )


class ValidationError(ApiError):
    def __init__(self, message: str, details=None):
        super().__init__(message, "VALIDATION_ERROR", 422, details)


def to_envelope(exc: ApiError) -> dict:
    body = {"error": {"code": exc.code, "message": exc.message}}
    if exc.details:
        body["error"]["details"] = exc.details
    return body