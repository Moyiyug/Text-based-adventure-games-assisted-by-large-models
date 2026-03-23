"""会话路由已挂载（不连真实 DB 业务流）。"""

from app.main import app


def test_sessions_routes_registered() -> None:
    paths = [getattr(r, "path", "") for r in app.routes]
    assert any(p.startswith("/api/sessions") for p in paths)
