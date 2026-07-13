from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS container_backups (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            tariff_id TEXT NOT NULL,
            backup_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_backups_user_id ON container_backups (user_id);
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS container_backups;")
