"""Added indexes for optimization

Revision ID: b7a2e01d1748
Revises: a08e52b697b7
Create Date: 2025-02-10 17:57:02.024768

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7a2e01d1748'
down_revision: Union[str, None] = 'a08e52b697b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    """Apply the migration: Add indexes for optimization."""
    op.create_index('idx_moderation_created_at', 'moderation_results', ['created_at'], unique=False)
    op.create_index('idx_moderation_status', 'moderation_results', ['status'], unique=False)
    op.create_index('idx_moderation_status_created_at', 'moderation_results', ['status', 'created_at'], unique=False)

def downgrade():
    """Rollback the migration: Remove indexes."""
    op.drop_index('idx_moderation_created_at', table_name='moderation_results')
    op.drop_index('idx_moderation_status', table_name='moderation_results')
    op.drop_index('idx_moderation_status_created_at', table_name='moderation_results')

