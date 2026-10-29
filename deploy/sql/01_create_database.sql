-- Misure: own database on the shared PostgreSQL server. No separate user: the application
-- connects with an existing server user (POSTGRES_USER / POSTGRES_PASSWORD in its .env).
-- Run once as a user with CREATEDB, e.g.:
--   psql -h <server> -U <user> -d postgres -v ON_ERROR_STOP=1 -f 01_create_database.sql

CREATE DATABASE misure
    ENCODING 'UTF8'
    TEMPLATE template0;
