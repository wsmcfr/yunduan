"""迁移 OpenClaudeCode 网关默认地址到米谱 API。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260421_0010"
down_revision = "20260421_0009"
branch_labels = None
depends_on = None


OLD_PRIMARY_BASE_URL = "https://www.openclaudecode.cn"
OLD_PRIMARY_V1_URL = "https://www.openclaudecode.cn/v1"
OLD_SLB_BASE_URL = "https://api-slb.openclaudecode.cn"
OLD_SLB_V1_URL = "https://api-slb.openclaudecode.cn/v1"
OLD_DOCS_URL = "https://docs.openclaudecode.cn/#/"
NEW_BASE_URL = "https://www.micuapi.ai"
NEW_V1_URL = "https://www.micuapi.ai/v1"


def upgrade() -> None:
    """把已有 OpenClaudeCode 网关和模型覆盖地址统一迁到米谱 API 域名。"""

    bind = op.get_bind()
    # 已保存的 OpenClaudeCode 网关可能仍指向旧主站或旧优选线路；统一改为新主站。
    bind.execute(
        sa.text(
            """
        UPDATE ai_gateways
        SET base_url = :new_base_url
        WHERE vendor = 'openclaudecode'
          AND base_url IN (:old_primary_base_url, :old_slb_base_url)
        """
        ),
        {
            "new_base_url": NEW_BASE_URL,
            "old_primary_base_url": OLD_PRIMARY_BASE_URL,
            "old_slb_base_url": OLD_SLB_BASE_URL,
        },
    )
    # 官网字段只是展示信息，但也应跟随服务商迁移，避免前端继续引导到旧文档站。
    bind.execute(
        sa.text(
            """
        UPDATE ai_gateways
        SET official_url = :new_base_url
        WHERE vendor = 'openclaudecode'
          AND official_url = :old_docs_url
        """
        ),
        {
            "new_base_url": NEW_BASE_URL,
            "old_docs_url": OLD_DOCS_URL,
        },
    )
    # Codex / Responses 模板历史上会保存带 /v1 的覆盖地址，运行时需要继续保持这一层路径。
    bind.execute(
        sa.text(
            """
        UPDATE ai_model_profiles
        SET base_url_override = :new_v1_url
        WHERE base_url_override IN (:old_primary_v1_url, :old_slb_v1_url)
        """
        ),
        {
            "new_v1_url": NEW_V1_URL,
            "old_primary_v1_url": OLD_PRIMARY_V1_URL,
            "old_slb_v1_url": OLD_SLB_V1_URL,
        },
    )


def downgrade() -> None:
    """回滚米谱 API 域名到历史 OpenClaudeCode 主站地址。"""

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
        UPDATE ai_gateways
        SET base_url = :old_primary_base_url
        WHERE vendor = 'openclaudecode'
          AND base_url = :new_base_url
        """
        ),
        {
            "old_primary_base_url": OLD_PRIMARY_BASE_URL,
            "new_base_url": NEW_BASE_URL,
        },
    )
    bind.execute(
        sa.text(
            """
        UPDATE ai_gateways
        SET official_url = :old_docs_url
        WHERE vendor = 'openclaudecode'
          AND official_url = :new_base_url
        """
        ),
        {
            "old_docs_url": OLD_DOCS_URL,
            "new_base_url": NEW_BASE_URL,
        },
    )
    bind.execute(
        sa.text(
            """
        UPDATE ai_model_profiles
        SET base_url_override = :old_primary_v1_url
        WHERE base_url_override = :new_v1_url
        """
        ),
        {
            "old_primary_v1_url": OLD_PRIMARY_V1_URL,
            "new_v1_url": NEW_V1_URL,
        },
    )
