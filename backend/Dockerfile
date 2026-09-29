# Build from the project root:  docker compose up --build
# (docker-compose.yml sets context "." so both backend/ and ai/ are available)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ai ./ai
COPY backend ./backend
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
