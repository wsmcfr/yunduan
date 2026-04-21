"""公司仓储实现。"""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from src.db.models.ai_gateway import AIGateway
from src.db.models.company import Company
from src.db.models.detection_record import DetectionRecord
from src.db.models.device import Device
from src.db.models.part import Part
from src.db.models.user import User


class CompanyRepository:
    """封装公司表的查询、统计与持久化逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求的数据库会话。"""

        self.db = db

    def _base_stmt(self) -> Select[tuple[Company]]:
        """返回公司查询基础语句。"""

        return select(Company)

    def get_by_id(self, company_id: int) -> Company | None:
        """按主键查询公司。"""

        return self.db.scalar(self._base_stmt().where(Company.id == company_id))

    def get_by_name(self, name: str) -> Company | None:
        """按公司名称查询公司。"""

        return self.db.scalar(self._base_stmt().where(Company.name == name))

    def get_by_invite_code(self, invite_code: str) -> Company | None:
        """按固定邀请码查询公司。"""

        return self.db.scalar(self._base_stmt().where(Company.invite_code == invite_code))

    def list_companies(
        self,
        *,
        keyword: str | None,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Company]]:
        """分页返回公司列表。"""

        stmt = self._base_stmt()
        normalized_keyword = (keyword or "").strip()
        if normalized_keyword:
            like_value = f"%{normalized_keyword}%"
            stmt = stmt.where(
                or_(
                    Company.name.ilike(like_value),
                    Company.contact_name.ilike(like_value),
                    Company.note.ilike(like_value),
                )
            )
        if is_active is not None:
            stmt = stmt.where(Company.is_active == is_active)

        total = int(self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        items = list(
            self.db.execute(
                stmt.order_by(Company.created_at.desc(), Company.id.desc()).offset(skip).limit(limit)
            ).scalars()
        )
        return total, items

    def summarize_company_usage(self, *, company_ids: list[int]) -> dict[int, dict[str, int]]:
        """汇总公司成员数、零件数、设备数、记录数和网关数。"""

        if not company_ids:
            return {}

        usage_map: dict[int, dict[str, int]] = {
            company_id: {
                "user_count": 0,
                "part_count": 0,
                "device_count": 0,
                "record_count": 0,
                "gateway_count": 0,
            }
            for company_id in company_ids
        }

        def apply_count(stmt, *, key: str) -> None:
            for row in self.db.execute(stmt):
                usage_map.setdefault(
                    int(row.company_id),
                    {
                        "user_count": 0,
                        "part_count": 0,
                        "device_count": 0,
                        "record_count": 0,
                        "gateway_count": 0,
                    },
                )[key] = int(row.count_value or 0)

        apply_count(
            select(User.company_id, func.count(User.id).label("count_value"))
            .where(User.company_id.in_(company_ids))
            .group_by(User.company_id),
            key="user_count",
        )
        apply_count(
            select(Part.company_id, func.count(Part.id).label("count_value"))
            .where(Part.company_id.in_(company_ids))
            .group_by(Part.company_id),
            key="part_count",
        )
        apply_count(
            select(Device.company_id, func.count(Device.id).label("count_value"))
            .where(Device.company_id.in_(company_ids))
            .group_by(Device.company_id),
            key="device_count",
        )
        apply_count(
            select(DetectionRecord.company_id, func.count(DetectionRecord.id).label("count_value"))
            .where(DetectionRecord.company_id.in_(company_ids))
            .group_by(DetectionRecord.company_id),
            key="record_count",
        )
        apply_count(
            select(AIGateway.company_id, func.count(AIGateway.id).label("count_value"))
            .where(AIGateway.company_id.in_(company_ids))
            .group_by(AIGateway.company_id),
            key="gateway_count",
        )

        return usage_map

    def create(self, company: Company) -> Company:
        """创建公司。"""

        self.db.add(company)
        self.db.flush()
        return company

    def save(self, company: Company) -> Company:
        """保存已存在的公司对象。"""

        self.db.add(company)
        self.db.flush()
        return company

    def delete(self, company: Company) -> None:
        """删除指定公司。"""

        self.db.delete(company)
