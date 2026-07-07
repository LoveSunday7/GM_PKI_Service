-- Manual migration: add columns that were defined in models but missing in DB
-- Execute: sqlite3 data.db < alembic/versions/add_crl_columns_manual.sql

ALTER TABLE crl_revocation ADD COLUMN first_published_crl INTEGER;
ALTER TABLE crl_publish ADD COLUMN is_delta BOOLEAN DEFAULT 0;
ALTER TABLE crl_publish ADD COLUMN base_crl_number INTEGER;
