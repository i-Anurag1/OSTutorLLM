from alembic import op
import sqlalchemy as sa
revision='0001'; down_revision=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.Integer,primary_key=True),sa.Column('email',sa.String(255),unique=True),sa.Column('password_hash',sa.String(255),nullable=False),sa.Column('name',sa.String(120),nullable=False),sa.Column('role',sa.String(30),nullable=False),sa.Column('created_at',sa.DateTime))
    op.create_table('topics',sa.Column('id',sa.Integer,primary_key=True),sa.Column('name',sa.String(120),unique=True),sa.Column('description',sa.Text),sa.Column('difficulty',sa.String(20)),sa.Column('active',sa.Boolean))
    op.create_table('progress',sa.Column('id',sa.Integer,primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id')),sa.Column('topic_id',sa.Integer,sa.ForeignKey('topics.id')),sa.Column('mastery',sa.Float),sa.Column('attempts',sa.Integer),sa.Column('correct',sa.Integer),sa.Column('updated_at',sa.DateTime))
    op.create_table('activities',sa.Column('id',sa.Integer,primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id')),sa.Column('kind',sa.String(40)),sa.Column('topic',sa.String(120)),sa.Column('score',sa.Float),sa.Column('payload',sa.JSON),sa.Column('created_at',sa.DateTime))
    op.create_table('chat_logs',sa.Column('id',sa.Integer,primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id')),sa.Column('question',sa.Text),sa.Column('answer',sa.Text),sa.Column('citations',sa.JSON),sa.Column('grounded',sa.Boolean),sa.Column('latency_ms',sa.Float),sa.Column('created_at',sa.DateTime))
    op.create_table('sources',sa.Column('id',sa.Integer,primary_key=True),sa.Column('name',sa.String(255)),sa.Column('path',sa.String(500),unique=True),sa.Column('status',sa.String(30)),sa.Column('version',sa.Integer),sa.Column('chunks',sa.Integer),sa.Column('checksum',sa.String(64)),sa.Column('uploaded_by',sa.Integer,sa.ForeignKey('users.id')),sa.Column('created_at',sa.DateTime))
    op.create_table('questions',sa.Column('id',sa.Integer,primary_key=True),sa.Column('topic',sa.String(120)),sa.Column('difficulty',sa.String(20)),sa.Column('kind',sa.String(20)),sa.Column('prompt',sa.Text),sa.Column('options',sa.JSON),sa.Column('answer',sa.Text),sa.Column('explanation',sa.Text),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id')),sa.Column('active',sa.Boolean))
    op.create_table('audit_logs',sa.Column('id',sa.Integer,primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id')),sa.Column('action',sa.String(100)),sa.Column('detail',sa.Text),sa.Column('created_at',sa.DateTime))
def downgrade():
    for t in ['audit_logs','questions','sources','chat_logs','activities','progress','topics','users']: op.drop_table(t)
