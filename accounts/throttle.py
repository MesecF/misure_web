"""
Protection against password guessing: after MAX_FAILURES failed logins of a username within
LOCK_MINUTES, that username is locked until the oldest of those failures is LOCK_MINUTES old.
Kept in the database, so it holds across gunicorn workers and restarts. Counted per username
(tenant + username), not per IP address: behind the reverse proxy all clients share its address.
"""

from datetime import timedelta

from django.utils import timezone

from .models import LoginFailure

MAX_FAILURES = 5
LOCK_MINUTES = 15


def failures(tenant, username):
    return LoginFailure.objects.filter(tenant=tenant, username=username)


def is_locked(tenant, username):
    since = timezone.now() - timedelta(minutes=LOCK_MINUTES)
    return failures(tenant, username).filter(failed_at__gte=since).count() >= MAX_FAILURES


def record_failure(tenant, username):
    LoginFailure.objects.create(tenant=tenant, username=username)
    # Old entries are of no use any more; this keeps the table small
    LoginFailure.objects.filter(failed_at__lt=timezone.now() - timedelta(days=1)).delete()


def clear_failures(tenant, username):
    failures(tenant, username).delete()
