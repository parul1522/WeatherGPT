"""Stored weather observations. Also used as a second-level cache for current weather."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base
from app.models.user import utc_now


class WeatherRecord(Base):
    __tablename__ = "weather_observations"
    __table_args__ = (Index("ix_weather_lat_lon_created", "latitude", "longitude", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    location_name: Mapped[str | None] = mapped_column(String(200))
    temperature: Mapped[float] = mapped_column(Float)
    feels_like: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[int | None] = mapped_column(Integer)
    wind_speed: Mapped[float | None] = mapped_column(Float)
    wind_direction: Mapped[int | None] = mapped_column(Integer)
    precipitation: Mapped[float | None] = mapped_column(Float)
    precipitation_probability: Mapped[int | None] = mapped_column(Integer)
    weather_code: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
