# Misure

Web application for entering and reviewing article measurements (multi-tenant).

Stack: Django 5.2, PostgreSQL 16, Django templates + HTMX, Bootstrap 5.

## Local development

Requirements: Python 3.13, Docker Desktop.

```powershell
# first time
Copy-Item .env.example .env        # then set DJANGO_SECRET_KEY and POSTGRES_PASSWORD
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

docker compose up -d
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser

# every time
docker compose up -d               # PostgreSQL on localhost:5432
.\.venv\Scripts\python.exe manage.py runserver
```

The app runs at http://localhost:8000, Django admin at http://localhost:8000/admin/.

Tests: `.\.venv\Scripts\python.exe manage.py test`

## Production (Docker on the server)

The image (`Dockerfile`) runs Django with gunicorn; whitenoise serves the static files. The
database is not in the container: it is PostgreSQL on a separate server (`deploy/sql/` creates
it once). On start the container applies new migrations.

Servers: application 10.24.131.36 (Docker, like the other applications there), database
10.24.131.35. The application is published on port 8084.

```powershell
# on the development machine: build and save the image (version in the tag)
docker build -t misure:1.0 .
docker save misure:1.0 -o misure-1.0.tar
```

Copy `misure-1.0.tar` to the application server, and create `/opt/misure/misure.env` there from
`deploy/env.example` (fill in, then `chmod 600 /opt/misure/misure.env`). Then:

```sh
docker load -i misure-1.0.tar
docker run -d --name misure --restart unless-stopped \
    -p 8084:8000 --env-file /opt/misure/misure.env misure:1.0
docker logs -f misure                                        # migrations, gunicorn started
docker exec -it misure python manage.py createsuperuser      # first installation only
```

Without a reverse proxy (testing): `http://10.24.131.36:8084`, with `DJANGO_HTTPS=False` and
`DJANGO_ALLOWED_HOSTS=10.24.131.36` in the env file. With a domain: the reverse proxy (nginx,
example in `deploy/nginx/misure.conf`) forwards to port 8084 and handles HTTPS; then
`DJANGO_HTTPS=True` and the domain in `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.
After changing the env file: `docker rm -f misure` and the same `docker run` again.

Update: build, save and load a new tag (`misure:1.1`), then `docker rm -f misure` and `docker run`
with the new tag. The previous image stays on the server for going back.

## Translations

The UI is in English (default), Croatian and Italian; translations are in `locale/<language>/LC_MESSAGES/django.po`,
the compiled `.mo` files are committed so the server does not need gettext. GNU gettext is not needed on Windows
either, the commands run in a temporary container:

```powershell
# after adding or changing texts: collect them into the .po files
docker run --rm -v "${PWD}:/app" -w /app python:3.13-slim sh -c "apt-get update -qq && apt-get install -y -qq gettext && pip install -q -r requirements.txt && python manage.py makemessages -l hr -l it --ignore=.venv --ignore=static/vendor"

# translate the new (empty msgstr) entries in both .po files, then compile.
# Also check entries marked "#, fuzzy": gettext guessed them from similar texts, they are usually wrong
# and are not used until the translation is corrected and the "fuzzy" flag removed.
docker run --rm -v "${PWD}:/app" -w /app python:3.13-slim sh -c "apt-get update -qq && apt-get install -y -qq gettext && pip install -q -r requirements.txt && python manage.py compilemessages --ignore=.venv"
```

## Users and tenants

- **Superadmin** (no tenant): logs into Django admin, creates tenants and their users.
- Each tenant has exactly one **admin** and one **user** account. Usernames are unique per tenant,
  so two tenants can both have a user called `admin`.
- Tenant data (categories, articles, elements, measurements) is read-only in Django admin; it is
  maintained by tenant admins in the application.
