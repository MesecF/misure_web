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
