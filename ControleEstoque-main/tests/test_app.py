import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_login_routes_by_role(monkeypatch):
    spec = importlib.util.spec_from_file_location("controle_app", ROOT / "conect.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def raise_error(*args, **kwargs):
        raise RuntimeError("MySQL indisponível")

    if hasattr(module, "mysql") and module.mysql is not None:
        monkeypatch.setattr(module.mysql.connector, "connect", raise_error)

    client = module.app.test_client()

    response = client.post(
        "/login",
        data={"email": "alice@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/contrl"

    response = client.post(
        "/login",
        data={"email": "bob@example.com", "password": "password456"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/estoque"

    response = client.get("/contrl")
    assert response.status_code == 302
    assert response.headers["Location"] == "/estoque"

    response = client.get("/exportar_excel?tipo=todos")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
