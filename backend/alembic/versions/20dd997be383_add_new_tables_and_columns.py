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


def upgrade() -> None:
    """Upgrade schema — add missing columns that exist on models but not in older DBs."""
    # Add first_published_crl to crl_revocation (C009: track first CRL that includes this revocation)
    with op.batch_alter_table('crl_revocation') as batch_op:
        batch_op.add_column(sa.Column('first_published_crl', sa.Integer(), nullable=True))
    # Add is_delta and base_crl_number to crl_publish (C008: Delta CRL support)
    with op.batch_alter_table('crl_publish') as batch_op:
        batch_op.add_column(sa.Column('is_delta', sa.Boolean(), server_default='0', nullable=True))
        batch_op.add_column(sa.Column('base_crl_number', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema — remove columns added above."""
    with op.batch_alter_table('crl_revocation') as batch_op:
        batch_op.drop_column('first_published_crl')
    with op.batch_alter_table('crl_publish') as batch_op:
        batch_op.drop_column('is_delta')
        batch_op.drop_column('base_crl_number')
