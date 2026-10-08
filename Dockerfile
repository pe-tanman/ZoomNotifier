FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY zoomnotifier ./zoomnotifier
ENV PORT=8000
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 "zoomnotifier.webhook:create_app()"
