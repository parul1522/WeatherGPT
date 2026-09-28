# Database Schema

- users(id, name, language, lat, lon, created_at)
- weather_snapshots(id, lat, lon, data jsonb, fetched_at)
- alerts(id, severity, title, description, region, starts_at, ends_at)
