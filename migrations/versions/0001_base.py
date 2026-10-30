"""Initial PostgreSQL storage, frozen independently of later Python models."""
from alembic import op

revision='0001_base'
down_revision=None
branch_labels=None
depends_on=None


def upgrade():
    statements=[
        '''CREATE TABLE cars (id VARCHAR PRIMARY KEY, characteristics JSON NOT NULL,
           daily_rate TEXT NOT NULL, hidden BOOLEAN NOT NULL DEFAULT false, rate_version INTEGER NOT NULL DEFAULT 0)''',
        '''CREATE TABLE accounts (id VARCHAR PRIMARY KEY, email TEXT NOT NULL, email_key TEXT NOT NULL UNIQUE,
           first_name TEXT NOT NULL,last_name TEXT NOT NULL,phone TEXT NOT NULL,password_hash TEXT NOT NULL,
           role VARCHAR NOT NULL DEFAULT 'client',failed_attempts INTEGER NOT NULL DEFAULT 0,blocked_until TIMESTAMPTZ)''',
        '''CREATE TABLE occupations (id VARCHAR PRIMARY KEY,car_id VARCHAR NOT NULL REFERENCES cars(id),
           starts_at TIMESTAMPTZ NOT NULL,ends_at TIMESTAMPTZ NOT NULL,kind VARCHAR NOT NULL)''',
        '''CREATE TABLE login_sessions (token_hash VARCHAR PRIMARY KEY,account_id VARCHAR NOT NULL REFERENCES accounts(id),
           created_at TIMESTAMPTZ NOT NULL,revoked BOOLEAN NOT NULL DEFAULT false)''',
        '''CREATE TABLE quotes (token_hash VARCHAR PRIMARY KEY,account_id VARCHAR NOT NULL REFERENCES accounts(id),
           car_id VARCHAR NOT NULL REFERENCES cars(id) ON DELETE CASCADE,starts_at TIMESTAMPTZ NOT NULL,ends_at TIMESTAMPTZ NOT NULL,
           rate_version INTEGER NOT NULL,daily_rate TEXT NOT NULL,days INTEGER NOT NULL,total TEXT NOT NULL)''',
        '''CREATE TABLE bookings (id VARCHAR PRIMARY KEY,car_id VARCHAR NOT NULL REFERENCES cars(id),account_id VARCHAR NOT NULL REFERENCES accounts(id),
           starts_at TIMESTAMPTZ NOT NULL,ends_at TIMESTAMPTZ NOT NULL,daily_rate TEXT NOT NULL,days INTEGER NOT NULL,total TEXT NOT NULL,
           cancelled BOOLEAN NOT NULL DEFAULT false,cancelled_at TIMESTAMPTZ,author_id VARCHAR REFERENCES accounts(id),author_role VARCHAR,reason TEXT)''',
        '''CREATE TABLE service_periods (id VARCHAR PRIMARY KEY,car_id VARCHAR NOT NULL REFERENCES cars(id),
           starts_at TIMESTAMPTZ NOT NULL,ends_at TIMESTAMPTZ NOT NULL,reason TEXT NOT NULL)''',
    ]
    for statement in statements:op.execute(statement)


def downgrade():
    raise RuntimeError('Destructive downgrade requires a separately reviewed recovery procedure')
