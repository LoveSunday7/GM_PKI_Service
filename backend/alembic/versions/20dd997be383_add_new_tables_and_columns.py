"""add_new_tables_and_columns

Revision ID: 20dd997be383
Revises: e632efb46135
Create Date: 2026-07-07 09:49:19.864082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20dd997be383'
down_revision: Union[str, Sequence[str], None] = 'e632efb46135'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    """Add a column only if it doesn't already exist (idempotent)."""
    import sqlalchemy as sa2
    conn = op.get_bind()
    inspector = sa2.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in existing:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(column)


def upgrade() -> None:
    """Upgrade schema — add missing columns (idempotent, safe for both fresh and existing DBs)."""
    _add_column_if_missing('crl_revocation', sa.Column('first_published_crl', sa.Integer(), nullable=True))
    _add_column_if_missing('crl_publish', sa.Column('is_delta', sa.Boolean(), server_default='0', nullable=True))
    _add_column_if_missing('crl_publish', sa.Column('base_crl_number', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema — remove added columns if they exist."""
    import sqlalchemy as sa2
    conn = op.get_bind()
    inspector = sa2.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns('crl_revocation')}
    if 'first_published_crl' in existing:
        with op.batch_alter_table('crl_revocation') as batch_op:
            batch_op.drop_column('first_published_crl')
    existing_pub = {c["name"] for c in inspector.get_columns('crl_publish')}
    if 'is_delta' in existing_pub:
        with op.batch_alter_table('crl_publish') as batch_op:
            batch_op.drop_column('is_delta')
    if 'base_crl_number' in existing_pub:
        with op.batch_alter_table('crl_publish') as batch_op:
            batch_op.drop_column('base_crl_number')
