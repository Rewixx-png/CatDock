"""add payment requests

Revision ID: 005
Revises: 004
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS payment_requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            method TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            details JSONB DEFAULT '{}'::jsonb,
            processed_by BIGINT,
            decline_reason TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_payment_requests_user_id ON payment_requests (user_id);
        CREATE INDEX IF NOT EXISTS idx_payment_requests_status ON payment_requests (status);
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payment_requests;")
