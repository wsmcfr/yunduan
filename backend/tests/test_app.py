"""后端应用基础 smoke test。"""

from __future__ import annotations

import asyncio
import unittest

from src.app import app


class AppSmokeTestCase(unittest.TestCase):
    """覆盖应用初始化后的基础健康检查与关键路由挂载。"""

    def test_healthcheck_returns_ok(self) -> None:
        """验证健康检查端点存在且可以直接返回最小成功结果。"""

        health_route = next(route for route in app.routes if route.path == "/health")
        response = asyncio.run(health_route.endpoint())

        self.assertEqual(response, {"status": "ok"})

    def test_manual_review_route_is_mounted_under_records_path(self) -> None:
        """验证人工复核最终路径确实挂在 `/api/v1/records` 前缀下。"""

        route_paths = {route.path for route in app.routes}

        self.assertIn("/api/v1/records/{record_id}/manual-review", route_paths)
        self.assertNotIn("/api/v1/reviews/records/{record_id}/manual-review", route_paths)

    def test_ai_chat_route_is_mounted_under_record_detail_path(self) -> None:
        """验证 AI 对话接口同样挂在当前记录上下文路径下。"""

        route_paths = {route.path for route in app.routes}

        self.assertIn("/api/v1/records/{record_id}/ai-chat", route_paths)

    def test_ai_gateway_discovery_route_is_mounted_under_settings_path(self) -> None:
        """验证模型自动探测接口已挂到 settings 路由下。"""

        route_paths = {route.path for route in app.routes}

        self.assertIn("/api/v1/settings/ai-gateways/{gateway_id}/discovered-models", route_paths)
        self.assertIn("/api/v1/settings/ai-gateways/discovery-preview", route_paths)
        self.assertIn("/api/v1/settings/users", route_paths)
        self.assertIn("/api/v1/settings/users/me/password-request", route_paths)
        self.assertIn("/api/v1/settings/users/{user_id}/ai-permission", route_paths)
        self.assertIn("/api/v1/settings/users/{user_id}/status", route_paths)
        self.assertIn("/api/v1/settings/users/{user_id}/password-reset", route_paths)
        self.assertIn("/api/v1/settings/users/{user_id}/password-request/approve", route_paths)
        self.assertIn("/api/v1/settings/users/{user_id}/password-request/reject", route_paths)
        self.assertIn("/api/v1/settings/users/{user_id}", route_paths)

    def test_auth_public_routes_are_mounted(self) -> None:
        """验证正式认证所需的公开路由都已经挂载。"""

        route_paths = {route.path for route in app.routes}

        self.assertIn("/api/v1/auth/runtime-options", route_paths)
        self.assertIn("/api/v1/auth/session", route_paths)
        self.assertIn("/api/v1/auth/register", route_paths)
        self.assertIn("/api/v1/auth/logout", route_paths)
        self.assertIn("/api/v1/auth/forgot-password", route_paths)
        self.assertIn("/api/v1/auth/reset-password", route_paths)

    def test_company_management_routes_are_mounted(self) -> None:
        """验证多租户公司管理与审批路由已挂载。"""

        route_paths = {route.path for route in app.routes}

        self.assertIn("/api/v1/companies/current", route_paths)
        self.assertIn("/api/v1/companies/current/reset-invite-code", route_paths)
        self.assertIn("/api/v1/companies", route_paths)
        self.assertIn("/api/v1/companies/admin-applications", route_paths)
        self.assertIn("/api/v1/companies/admin-applications/{user_id}/approve", route_paths)

    def test_device_delete_route_is_mounted(self) -> None:
        """验证设备彻底删除接口挂载在设备管理资源路径下。"""

        device_routes = [
            route
            for route in app.routes
            if route.path == "/api/v1/devices/{device_id}"
        ]

        self.assertTrue(any("DELETE" in getattr(route, "methods", set()) for route in device_routes))
