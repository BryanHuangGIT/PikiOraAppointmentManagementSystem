
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files using temporary build settings
RUN DEBUG=True SECRET_KEY=temporary-build-only-key \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Apply migrations and start Django
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn pikioraappointmentmanagementsystem.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
