"""create initial tables

Revision ID: 2a5b89eda26e
Revises: 
Create Date: 2026-11-18 21:06:27.931009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2a5b89eda26e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('companies',
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('plan', sa.String(length=20), server_default='basic', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("plan IN ('basic','pro','business')", name=op.f('ck_companies_plan_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_companies'))
    )
    op.create_table('users',
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), server_default='member', nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('admin','manager','member')", name=op.f('ck_users_role_valid')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_users_company_id_companies')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_index(op.f('ix_users_company_id'), 'users', ['company_id'], unique=False)
    op.create_table('customers',
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('organization', sa.String(length=150), nullable=True),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('stage', sa.String(length=20), server_default='lead', nullable=False),
    sa.Column('source', sa.String(length=30), nullable=True),
    sa.Column('tags', postgresql.ARRAY(sa.String(length=50)), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('owner_id', sa.Uuid(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("stage IN ('lead','qualified','proposal','negotiation','won','lost')", name=op.f('ck_customers_stage_valid')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_customers_company_id_companies')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_customers_created_by_users')),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_customers_owner_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_customers'))
    )
    op.create_index('ix_customers_company_name', 'customers', ['company_id', 'name'], unique=False)
    op.create_index('ix_customers_company_owner', 'customers', ['company_id', 'owner_id'], unique=False)
    op.create_index('ix_customers_company_stage', 'customers', ['company_id', 'stage'], unique=False)
    op.create_index('uq_customers_company_email', 'customers', ['company_id', 'email'], unique=True, postgresql_where=sa.text('email IS NOT NULL AND deleted_at IS NULL'))
    op.create_table('tasks',
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='todo', nullable=False),
    sa.Column('priority', sa.String(length=10), server_default='medium', nullable=False),
    sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('remind_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('assignee_id', sa.Uuid(), nullable=True),
    sa.Column('customer_id', sa.Uuid(), nullable=True),
    sa.Column('record_id', sa.Uuid(), nullable=True),
    sa.Column('source', sa.String(length=20), server_default='manual', nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("priority IN ('low','medium','high','urgent')", name=op.f('ck_tasks_priority_valid')),
    sa.CheckConstraint("source IN ('manual','ai_agent','automation')", name=op.f('ck_tasks_source_valid')),
    sa.CheckConstraint("status IN ('todo','in_progress','done','cancelled')", name=op.f('ck_tasks_status_valid')),
    sa.ForeignKeyConstraint(['assignee_id'], ['users.id'], name=op.f('fk_tasks_assignee_id_users')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_tasks_company_id_companies')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_tasks_created_by_users')),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_tasks_customer_id_customers')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tasks'))
    )
    op.create_index('ix_tasks_company_assignee', 'tasks', ['company_id', 'assignee_id'], unique=False)
    op.create_index('ix_tasks_company_customer', 'tasks', ['company_id', 'customer_id'], unique=False)
    op.create_index('ix_tasks_company_due_date', 'tasks', ['company_id', 'due_date'], unique=False)
    op.create_index('ix_tasks_company_status', 'tasks', ['company_id', 'status'], unique=False)
    op.create_table('records',
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('reference_no', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=3), server_default='USD', nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=True),
    sa.Column('task_id', sa.Uuid(), nullable=True),
    sa.Column('source', sa.String(length=20), server_default='manual', nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("source IN ('manual','ai_agent','automation')", name=op.f('ck_records_source_valid')),
    sa.CheckConstraint("type IN ('quotation','invoice','payment','meeting_summary','note','activity')", name=op.f('ck_records_type_valid')),
    sa.CheckConstraint('amount IS NULL OR amount >= 0', name=op.f('ck_records_amount_non_negative')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_records_company_id_companies')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_records_created_by_users')),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_records_customer_id_customers')),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name=op.f('fk_records_task_id_tasks')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_records'))
    )
    op.create_index('ix_records_company_created_at', 'records', ['company_id', 'created_at'], unique=False)
    op.create_index('ix_records_company_customer', 'records', ['company_id', 'customer_id'], unique=False)
    op.create_index('ix_records_company_status', 'records', ['company_id', 'status'], unique=False)
    op.create_index('ix_records_company_type', 'records', ['company_id', 'type'], unique=False)
    op.create_index('uq_records_company_type_reference', 'records', ['company_id', 'type', 'reference_no'], unique=True, postgresql_where=sa.text('reference_no IS NOT NULL AND deleted_at IS NULL'))

    # tasks <-> records point at each other, so this foreign key is added
    # after both tables exist.
    op.create_foreign_key(
        'fk_tasks_record_id_records', 'tasks', 'records', ['record_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the circular foreign key first, so the tables can be dropped.
    op.drop_constraint('fk_tasks_record_id_records', 'tasks', type_='foreignkey')

    op.drop_index('uq_records_company_type_reference', table_name='records', postgresql_where=sa.text('reference_no IS NOT NULL AND deleted_at IS NULL'))
    op.drop_index('ix_records_company_type', table_name='records')
    op.drop_index('ix_records_company_status', table_name='records')
    op.drop_index('ix_records_company_customer', table_name='records')
    op.drop_index('ix_records_company_created_at', table_name='records')
    op.drop_table('records')
    op.drop_index('ix_tasks_company_status', table_name='tasks')
    op.drop_index('ix_tasks_company_due_date', table_name='tasks')
    op.drop_index('ix_tasks_company_customer', table_name='tasks')
    op.drop_index('ix_tasks_company_assignee', table_name='tasks')
    op.drop_table('tasks')
    op.drop_index('uq_customers_company_email', table_name='customers', postgresql_where=sa.text('email IS NOT NULL AND deleted_at IS NULL'))
    op.drop_index('ix_customers_company_stage', table_name='customers')
    op.drop_index('ix_customers_company_owner', table_name='customers')
    op.drop_index('ix_customers_company_name', table_name='customers')
    op.drop_table('customers')
    op.drop_index(op.f('ix_users_company_id'), table_name='users')
    op.drop_table('users')
    op.drop_table('companies')