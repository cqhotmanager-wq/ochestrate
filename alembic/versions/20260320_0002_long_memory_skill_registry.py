from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260320_0002"
down_revision = "20260316_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_registry_entries (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          tenant_id VARCHAR(64) NOT NULL,
          skill_name VARCHAR(128) NOT NULL,
          description TEXT NOT NULL,
          skill_path TEXT NOT NULL,
          tools_json JSON NULL,
          embedding_json JSON NULL,
          source VARCHAR(32) NOT NULL DEFAULT 'skill_md',
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_skill_registry_name (tenant_id, skill_name),
          KEY idx_skill_registry_tenant (tenant_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS long_term_memories (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          tenant_id VARCHAR(64) NOT NULL,
          user_id VARCHAR(64) NOT NULL,
          task TEXT NOT NULL,
          solution TEXT NOT NULL,
          success TINYINT(1) NOT NULL,
          lessons_learned TEXT NULL,
          tags_json JSON NULL,
          embedding_json JSON NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          expires_at DATETIME NOT NULL,
          KEY idx_long_memory_scope (tenant_id, user_id, expires_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS long_term_memories")
    op.execute("DROP TABLE IF EXISTS skill_registry_entries")
