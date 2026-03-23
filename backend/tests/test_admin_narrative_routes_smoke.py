"""管理端 prompts/sessions 路由已挂载。"""

from app.main import app


def test_admin_prompts_and_sessions_routes() -> None:
    paths = [getattr(r, "path", "") for r in app.routes]
    assert any("/api/admin/prompts" in p for p in paths)
    assert any(p.startswith("/api/admin/sessions") for p in paths)
