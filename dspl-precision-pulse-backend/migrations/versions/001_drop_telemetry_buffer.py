"""drop telemetry_buffer table

Revision ID: 001_drop_telemetry_buffer
Revises:
Create Date: 2025-01-01 00:00:00.000000

The telemetry_buffer table was created by the ORM model but is never
queried by any route, service, or background task. All offline buffering
for the desktop streamer is handled via the desktop's own SQLite
local_buffer / parameter_stream / telemetry_buffer tables.
"""

import sqlalchemy as sa
from alembic import op

revision = '001_drop_telemetry_buffer'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('telemetry_buffer')


def downgrade():
    op.create_table(
        'telemetry_buffer',
        sa.Column('id',             sa.Integer(),       primary_key=True),
        sa.Column('device_id',      sa.String(255),     nullable=False),
        sa.Column('parameter_id',   sa.Integer(),       nullable=False),
        sa.Column('parameter_name', sa.String(255),     nullable=False),
        sa.Column('value',          sa.Float(),         nullable=False),
        sa.Column('unit',           sa.String(50),      nullable=True),
        sa.Column('timestamp',      sa.DateTime(),      nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('synced',         sa.Boolean(),       nullable=False,
                  server_default=sa.text('FALSE')),
    )
    op.create_index('ix_telemetry_buffer_device_id',  'telemetry_buffer', ['device_id'])
    op.create_index('ix_telemetry_buffer_timestamp',  'telemetry_buffer', ['timestamp'])
    op.create_index('ix_telemetry_buffer_synced',     'telemetry_buffer', ['synced'])
