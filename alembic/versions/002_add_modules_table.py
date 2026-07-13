from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_modules (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            filename TEXT NOT NULL,
            local_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            saved_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_user_modules_user_id ON user_modules (user_id);
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_modules;")
