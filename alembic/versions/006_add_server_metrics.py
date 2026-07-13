"""add server metrics

Revision ID: 006
Revises: 005
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS server_metrics (
            id SERIAL PRIMARY KEY,
            server_id TEXT NOT NULL,
            cpu_usage DOUBLE PRECISION DEFAULT 0.0,
            ram_usage DOUBLE PRECISION DEFAULT 0.0,
            disk_usage DOUBLE PRECISION DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        -- Индекс для быстрого поиска по времени и серверу
        CREATE INDEX IF NOT EXISTS idx_metrics_server_date ON server_metrics (server_id, created_at);
        -- Индекс для автоматической очистки старых данных (если понадобится)
        CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON server_metrics (created_at);
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS server_metrics;")
