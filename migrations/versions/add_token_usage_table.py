"""Add token usage table

Revision ID: e18c51b9e4d3
Revises: e17b51a9e4d2
Create Date: 2025-05-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e18c51b9e4d3'
down_revision = 'e17b51a9e4d2'
branch_labels = None
depends_on = None


def upgrade():
    # Create token_usage table for PostgreSQL
    op.create_table('token_usage',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=True),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('completion_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('request_type', sa.String(50), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('cost_per_token', sa.Float(), nullable=True),
        sa.Column('request_data', sa.Text(), nullable=True),
        sa.Column('response_data', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better performance
    op.create_index(op.f('ix_token_usage_session_id'), 'token_usage', ['session_id'], unique=False)
    op.create_index(op.f('ix_token_usage_user_id'), 'token_usage', ['user_id'], unique=False)
    op.create_index(op.f('ix_token_usage_timestamp'), 'token_usage', ['timestamp'], unique=False)
    op.create_index(op.f('ix_token_usage_model'), 'token_usage', ['model'], unique=False)
    op.create_index(op.f('ix_token_usage_provider'), 'token_usage', ['provider'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_token_usage_provider'), table_name='token_usage')
    op.drop_index(op.f('ix_token_usage_model'), table_name='token_usage')
    op.drop_index(op.f('ix_token_usage_timestamp'), table_name='token_usage')
    op.drop_index(op.f('ix_token_usage_user_id'), table_name='token_usage')
    op.drop_index(op.f('ix_token_usage_session_id'), table_name='token_usage')
    op.drop_table('token_usage')
