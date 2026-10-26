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

## Users and tenants

- **Superadmin** (no tenant): logs into Django admin, creates tenants and their users.
- Each tenant has exactly one **admin** and one **user** account. Usernames are unique per tenant,
  so two tenants can both have a user called `admin`.
- Tenant data (brands, articles, elements, measurements) is read-only in Django admin; it is
  maintained by tenant admins in the application.
