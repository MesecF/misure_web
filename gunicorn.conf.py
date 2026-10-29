# gunicorn settings for the container (Dockerfile); loaded automatically from the working directory.
import os

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')

# 4 processes with 2 threads each: 8 requests at a time, so a long export does not block entry
workers = 4
threads = 2

# Large exports; nginx waits a little longer (proxy_read_timeout 130s)
timeout = 120

# Access log to the container log; the client address comes from the reverse proxy
# (X-Forwarded-For), the direct peer would always be the proxy itself
accesslog = '-'
access_log_format = '%({x-forwarded-for}i)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'
