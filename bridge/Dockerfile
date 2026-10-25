FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin riri \
    && mkdir -p /data \
    && chown riri:riri /data
COPY . /app/bridge/
USER riri

EXPOSE 8000
CMD ["uvicorn", "bridge.app:app", "--host", "0.0.0.0", "--port", "8000"]
