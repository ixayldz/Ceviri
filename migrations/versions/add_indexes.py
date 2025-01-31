"""add_indexes

Revision ID: add_indexes_001
Revises: initial_migration
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_indexes_001'
down_revision = 'initial_migration'
branch_labels = None
depends_on = None

def upgrade():
    # Kullanıcı tablosu indeksleri
    op.create_index('idx_user_email', 'users', ['email'], unique=True)
    op.create_index('idx_user_target_language', 'users', ['target_language'])
    
    # Çeviri geçmişi tablosu indeksleri
    op.create_index(
        'idx_translation_history_user_id',
        'translation_history',
        ['user_id']
    )
    op.create_index(
        'idx_translation_history_created_at',
        'translation_history',
        ['created_at']
    )
    op.create_index(
        'idx_translation_history_source_language',
        'translation_history',
        ['source_language']
    )
    op.create_index(
        'idx_translation_history_target_language',
        'translation_history',
        ['target_language']
    )
    
    # Composite indeksler
    op.create_index(
        'idx_translation_history_user_date',
        'translation_history',
        ['user_id', 'created_at']
    )
    op.create_index(
        'idx_translation_history_languages',
        'translation_history',
        ['source_language', 'target_language']
    )

def downgrade():
    # İndeksleri kaldır
    op.drop_index('idx_user_email')
    op.drop_index('idx_user_target_language')
    op.drop_index('idx_translation_history_user_id')
    op.drop_index('idx_translation_history_created_at')
    op.drop_index('idx_translation_history_source_language')
    op.drop_index('idx_translation_history_target_language')
    op.drop_index('idx_translation_history_user_date')
    op.drop_index('idx_translation_history_languages') 