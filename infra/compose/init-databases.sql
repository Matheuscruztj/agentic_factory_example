SELECT 'CREATE DATABASE customer_registry OWNER ' || quote_ident(current_user)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'customer_registry')\gexec
