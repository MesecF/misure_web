# Production image: Django with gunicorn. The database is outside the container (PostgreSQL
# on the server); settings come from an env file at run time (deploy/env.example).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Static files are collected into the image; whitenoise serves them. The key is only needed
# for loading the settings here, the real one comes from the env file.
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
    && useradd --system --create-home misure

USER misure

EXPOSE 8000

# Applies new migrations (nothing to do when the database is up to date), then starts gunicorn
# with the settings in gunicorn.conf.py (port 8000 in the container, published with docker run -p).
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi"]
