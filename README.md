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

# every time
docker compose up -d               # PostgreSQL on localhost:5432
.\.venv\Scripts\python.exe manage.py runserver
```

The app runs at http://localhost:8000.
