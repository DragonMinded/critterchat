"""Add primary keys where necessary, part 1.

Revision ID: 08469a133de7
Revises: 1acf5383e9ee
Create Date: 2025-06-30 21:57:38.479661

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '08469a133de7'
down_revision = '1acf5383e9ee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('profile', 'id')
    op.drop_column('session', 'id')
    op.drop_column('settings', 'id')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('settings', sa.Column('id', mysql.INTEGER(), autoincrement=False, nullable=False))
    op.add_column('session', sa.Column('id', mysql.INTEGER(), autoincrement=False, nullable=False))
    op.add_column('profile', sa.Column('id', mysql.INTEGER(), autoincrement=False, nullable=False))
    # ### end Alembic commands ###
