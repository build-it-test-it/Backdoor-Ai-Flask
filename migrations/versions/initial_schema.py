"""Initial database schema

Revision ID: e17b51a9e4d2
Revises: 
Create Date: 2025-05-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e17b51a9e4d2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create agent_role and agent_status enum types for PostgreSQL
    op.create_table('context_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('item_type', sa.String(length=50), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('ttl', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('is_expired', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_context_items_is_expired'), 'context_items', ['is_expired'], unique=False)
    op.create_index(op.f('ix_context_items_item_type'), 'context_items', ['item_type'], unique=False)
    op.create_index(op.f('ix_context_items_session_id'), 'context_items', ['session_id'], unique=False)
    
    op.create_table('agents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('role', sa.Enum('DEFAULT', 'SYSTEM', 'ASSISTANT', 'USER', 'TOOL', 'ADMIN', name='agentrole'), nullable=False),
        sa.Column('status', sa.Enum('READY', 'BUSY', 'IDLE', 'ERROR', 'OFFLINE', name='agentstatus'), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_active', sa.DateTime(), nullable=True),
        sa.Column('memory', sa.JSON(), nullable=True),
        sa.Column('tool_permissions', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agents_session_id'), 'agents', ['session_id'], unique=False)
    
    op.create_table('tool_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('result_data', sa.JSON(), nullable=False),
        sa.Column('output_text', sa.Text(), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_session_id'), 'tasks', ['session_id'], unique=False)
    
    op.create_table('tool_usages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tool_type', sa.String(length=50), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('result_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['result_id'], ['tool_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tool_usages_session_id'), 'tool_usages', ['session_id'], unique=False)
    op.create_index(op.f('ix_tool_usages_tool_type'), 'tool_usages', ['tool_type'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tool_usages_tool_type'), table_name='tool_usages')
    op.drop_index(op.f('ix_tool_usages_session_id'), table_name='tool_usages')
    op.drop_table('tool_usages')
    op.drop_index(op.f('ix_tasks_session_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_table('tool_results')
    op.drop_index(op.f('ix_agents_session_id'), table_name='agents')
    op.drop_table('agents')
    op.drop_index(op.f('ix_context_items_session_id'), table_name='context_items')
    op.drop_index(op.f('ix_context_items_item_type'), table_name='context_items')
    op.drop_index(op.f('ix_context_items_is_expired'), table_name='context_items')
    op.drop_table('context_items')
    sa.Enum(name='agentrole').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='agentstatus').drop(op.get_bind(), checkfirst=False)
