"""Reusable database operations. Services call these; API routes never touch the database directly."""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Conversation, WeatherRecord
from app.schemas.alert import AlertItem
from app.schemas.weather import CurrentConditions


def _utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; everything is stored in UTC, so re-attach it.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def save_weather(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    location_name: str | None,
    conditions: CurrentConditions,
    observed_at: datetime,
    source: str,
    precipitation_probability: int | None = None,
) -> WeatherRecord:
    record = WeatherRecord(
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        temperature=conditions.temperature,
        feels_like=conditions.feels_like,
        humidity=conditions.humidity,
        wind_speed=conditions.wind_speed,
        wind_direction=conditions.wind_direction,
        precipitation=conditions.precipitation,
        precipitation_probability=precipitation_probability,
        weather_code=conditions.weather_code,
        observed_at=_utc(observed_at),
        source=source,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_recent_weather(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    max_age_seconds: int,
    tolerance_degrees: float = 0.01,
) -> WeatherRecord | None:
    """Latest observation fetched within `max_age_seconds` near the given point (~1 km box)."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    stmt = (
        select(WeatherRecord)
        .where(
            WeatherRecord.latitude.between(latitude - tolerance_degrees, latitude + tolerance_degrees),
            WeatherRecord.longitude.between(longitude - tolerance_degrees, longitude + tolerance_degrees),
            WeatherRecord.created_at >= cutoff,
        )
        .order_by(WeatherRecord.created_at.desc())
        .limit(1)
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is not None:
        record.observed_at = _utc(record.observed_at)
        record.created_at = _utc(record.created_at)
    return record


async def save_alerts(
    db: AsyncSession,
    alerts: list[AlertItem],
    *,
    latitude: float,
    longitude: float,
    location_name: str | None,
) -> int:
    """Insert official alerts, skipping ones already stored (same source + external_id). Returns count added."""
    added = 0
    for item in alerts:
        if item.external_id:
            existing = await db.execute(
                select(Alert.id).where(Alert.source == item.source, Alert.external_id == item.external_id)
            )
            if existing.first() is not None:
                continue
        db.add(
            Alert(
                external_id=item.external_id,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                alert_type=item.alert_type,
                severity=item.severity,
                title=item.title,
                description=item.description,
                source=item.source,
                valid_from=_utc(item.valid_from) if item.valid_from else None,
                valid_until=_utc(item.valid_until) if item.valid_until else None,
            )
        )
        added += 1
    await db.commit()
    return added


async def get_active_alerts(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    radius_degrees: float = 0.5,
) -> list[AlertItem]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(Alert)
        .where(
            Alert.latitude.between(latitude - radius_degrees, latitude + radius_degrees),
            Alert.longitude.between(longitude - radius_degrees, longitude + radius_degrees),
            or_(Alert.valid_from.is_(None), Alert.valid_from <= now),
            or_(Alert.valid_until.is_(None), Alert.valid_until >= now),
        )
        .order_by(Alert.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        AlertItem(
            external_id=row.external_id,
            alert_type=row.alert_type,
            severity=row.severity,
            title=row.title,
            description=row.description,
            source=row.source,
            valid_from=_utc(row.valid_from) if row.valid_from else None,
            valid_until=_utc(row.valid_until) if row.valid_until else None,
        )
        for row in rows
    ]


async def save_conversation(
    db: AsyncSession,
    *,
    message: str,
    answer: str,
    language: str,
    intent: dict[str, Any] | None,
    session_id: str | None = None,
    location_name: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    user_id: int | None = None,
) -> Conversation:
    conversation = Conversation(
        user_id=user_id,
        session_id=session_id,
        message=message,
        answer=answer,
        language=language,
        intent=intent,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def safe_rollback(db: AsyncSession) -> None:
    """Roll back after a failed write without raising if the connection itself is broken."""
    try:
        await db.rollback()
    except (SQLAlchemyError, OSError):
        pass
