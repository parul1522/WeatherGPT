from pydantic import BaseModel


class CurrentWeather(BaseModel):
    temperature: float
    humidity: float | None = None
    wind_speed: float | None = None
    condition: str | None = None
