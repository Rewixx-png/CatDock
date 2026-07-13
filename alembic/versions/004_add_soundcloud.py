from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS soundcloud_token TEXT;")

def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS soundcloud_token;")
