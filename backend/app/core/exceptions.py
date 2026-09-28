"""Application errors. Each maps to an HTTP status and a stable error code for the frontend."""


class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        self.message = message or self.default_message
        if code:
            self.code = code
        super().__init__(self.message)


class InvalidRequestError(AppError):
    status_code = 400
    code = "INVALID_REQUEST"
    default_message = "The request is invalid."


class AuthenticationError(AppError):
    status_code = 401
    code = "INVALID_API_KEY"
    default_message = "A valid X-API-Key header is required."


class LocationNotFoundError(AppError):
    status_code = 404
    code = "LOCATION_NOT_FOUND"
    default_message = "Location not found."


class ExternalServiceError(AppError):
    status_code = 502
    code = "EXTERNAL_SERVICE_UNAVAILABLE"
    default_message = "An external service is unavailable."


class WeatherProviderError(ExternalServiceError):
    code = "WEATHER_PROVIDER_UNAVAILABLE"
    default_message = "Weather provider unavailable. Please try again shortly."


class GeocodingProviderError(ExternalServiceError):
    code = "GEOCODING_PROVIDER_UNAVAILABLE"
    default_message = "Location search is unavailable. Please try again shortly."


class AlertProviderError(ExternalServiceError):
    code = "ALERT_PROVIDER_UNAVAILABLE"
    default_message = "Alert provider unavailable."


class AIServiceUnavailableError(ExternalServiceError):
    status_code = 503
    code = "AI_SERVICE_UNAVAILABLE"
    default_message = "AI service unavailable. Please try again shortly."


class AIInvalidResponseError(AppError):
    status_code = 502
    code = "AI_INVALID_RESPONSE"
    default_message = "The AI service returned an unusable response. Please try again."
