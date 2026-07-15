from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QUrl

from app.main import is_valid_picker_target
from app.web_window import (
    LocalOnlyInterceptor,
    WebMainWindow,
    is_allowed_local_url,
    parse_frontend_exchange,
)


class FakeRequestInfo:
    def __init__(self, url: QUrl) -> None:
        self._url = url
        self.blocked = False

    def requestUrl(self) -> QUrl:  # noqa: N802
        return self._url

    def block(self, blocked: bool) -> None:
        self.blocked = blocked


def test_local_url_policy_restricts_files_to_frontend_root(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    index = frontend / "index.html"
    index.write_text("ok", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("secret", encoding="utf-8")

    assert is_allowed_local_url(QUrl.fromLocalFile(str(index)), frontend)
    assert not is_allowed_local_url(QUrl.fromLocalFile(str(secret)), frontend)
    assert not is_allowed_local_url(QUrl("https://example.com"), frontend)
    assert is_allowed_local_url(QUrl("qrc:///qtwebchannel/qwebchannel.js"), frontend)


def test_request_interceptor_blocks_file_outside_bundle(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    request = FakeRequestInfo(QUrl.fromLocalFile(str(tmp_path / "private.txt")))
    interceptor = LocalOnlyInterceptor(frontend)
    interceptor.interceptRequest(request)
    assert request.blocked is True


def test_picker_target_must_be_directly_inside_temp_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.tempfile.gettempdir", lambda: str(tmp_path))
    assert is_valid_picker_target(str(tmp_path / "ruralfindme-picker-safe.json"))
    assert not is_valid_picker_target(str(tmp_path / "other.json"))
    nested = tmp_path / "nested"
    nested.mkdir()
    assert not is_valid_picker_target(str(nested / "ruralfindme-picker-unsafe.json"))


def test_frontend_exchange_accepts_only_typed_bounded_commands():
    raw_commands = [{"name": f"command-{index}", "args": []} for index in range(25)]
    raw_commands.insert(1, {"name": 42, "args": "invalid"})
    ready, commands = parse_frontend_exchange(
        __import__("json").dumps({"ready": True, "commands": raw_commands})
    )
    assert ready is True
    assert len(commands) == 19
    assert all(isinstance(name, str) and isinstance(args, list) for name, args in commands)
    assert parse_frontend_exchange("not-json") is None


def test_close_event_clears_sensitive_browser_state():
    calls = []

    class FakeTimer:
        def stop(self): calls.append("timer")

    class FakeBridge:
        def clear_sensitive_state(self): calls.append("bridge")

    class FakeCookies:
        def deleteAllCookies(self): calls.append("cookies")

    class FakeProfile:
        def clearHttpCache(self): calls.append("cache")
        def cookieStore(self): return FakeCookies()

    class FakeView:
        def setPage(self, page):
            assert page is None
            calls.append("page")

    class FakeEvent:
        def accept(self): calls.append("event")

    window = SimpleNamespace(
        request_timer=FakeTimer(), bridge=FakeBridge(), profile=FakeProfile(), view=FakeView()
    )
    WebMainWindow.closeEvent(window, FakeEvent())
    assert calls == ["timer", "bridge", "cache", "cookies", "page", "event"]
