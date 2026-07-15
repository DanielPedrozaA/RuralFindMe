from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

from app.bridge import DesktopBridge
from app.config import resource_path


def is_allowed_local_url(url: QUrl, allowed_file_root: Path) -> bool:
    scheme = url.scheme().lower()
    if scheme not in LocalOnlyInterceptor.ALLOWED_SCHEMES:
        return False
    if scheme != "file":
        return True
    try:
        root = allowed_file_root.resolve(strict=True)
        candidate = Path(url.toLocalFile()).resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    return candidate == root or root in candidate.parents


def parse_frontend_exchange(payload: object) -> tuple[bool, list[tuple[str, list[object]]]] | None:
    if not isinstance(payload, str):
        return None
    try:
        exchange = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(exchange, dict):
        return None
    commands: list[tuple[str, list[object]]] = []
    raw_commands = exchange.get("commands")
    if isinstance(raw_commands, list):
        for command in raw_commands[:20]:
            if not isinstance(command, dict):
                continue
            name = command.get("name")
            args = command.get("args", [])
            if isinstance(name, str) and isinstance(args, list):
                commands.append((name, args))
    return exchange.get("ready") is True, commands


class LocalOnlyInterceptor(QWebEngineUrlRequestInterceptor):
    ALLOWED_SCHEMES = {"file", "qrc", "data", "blob"}

    def __init__(self, allowed_file_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.allowed_file_root = allowed_file_root

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        if not is_allowed_local_url(info.requestUrl(), self.allowed_file_root):
            info.block(True)


class LocalPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, parent, allowed_file_root: Path) -> None:
        super().__init__(profile, parent)
        self.allowed_file_root = allowed_file_root

    def acceptNavigationRequest(  # noqa: N802
        self,
        url: QUrl,
        navigation_type: QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        del navigation_type, is_main_frame
        return is_allowed_local_url(url, self.allowed_file_root)


class WebMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RuralFindMe — Resultado SSO")
        self.setMinimumSize(1040, 700)
        self.resize(1280, 820)

        frontend = resource_path("frontend/dist/index.html")
        if not frontend.exists():
            raise RuntimeError(
                "No se encontró frontend/dist/index.html. Ejecute `npm run build` en frontend."
            )
        frontend_root = frontend.parent.resolve()

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.profile = QWebEngineProfile("RuralFindMeMemoryProfile", self)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self.interceptor = LocalOnlyInterceptor(frontend_root, self)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.page = LocalPage(self.profile, self.view, frontend_root)
        self.view.setPage(self.page)

        settings = self.page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False
        )
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)

        self.channel = QWebChannel(self.page)
        self.bridge = DesktopBridge(self, self.channel)
        self.channel.registerObject("backend", self.bridge)
        self.page.setWebChannel(self.channel)

        self._frontend_events: list[dict[str, object]] = []
        self._poll_event_count = 0
        self.bridge.stateSnapshot.connect(
            lambda payload: self._queue_frontend_event("stateSnapshot", payload)
        )
        self.bridge.documentSelected.connect(
            lambda slot, payload: self._queue_frontend_event(
                "documentSelected", slot, payload
            )
        )
        self.bridge.documentBatchStateChanged.connect(
            lambda busy, message: self._queue_frontend_event(
                "documentBatchStateChanged", busy, message
            )
        )
        self.bridge.documentValidationUpdated.connect(
            lambda payload: self._queue_frontend_event(
                "documentValidationUpdated", payload
            )
        )
        self.bridge.processingStageChanged.connect(
            lambda stage, message: self._queue_frontend_event(
                "processingStageChanged", stage, message
            )
        )
        self.bridge.searchCompleted.connect(
            lambda payload: self._queue_frontend_event("searchCompleted", payload)
        )
        self.bridge.processingFailed.connect(
            lambda message: self._queue_frontend_event("processingFailed", message)
        )
        self.bridge.exportCompleted.connect(
            lambda message: self._queue_frontend_event("exportCompleted", message)
        )

        self._request_poll_in_flight = False
        self.request_timer = QTimer(self)
        self.request_timer.setInterval(250)
        self.request_timer.timeout.connect(self._poll_frontend_requests)

        self.profile.downloadRequested.connect(lambda request: request.cancel())
        self.view.loadFinished.connect(
            lambda loaded: self.request_timer.start() if loaded else None
        )
        self.bridge.initialize()
        self.view.load(QUrl.fromLocalFile(str(frontend.resolve())))

    def _queue_frontend_event(self, name: str, *args: object) -> None:
        self._frontend_events.append({"name": name, "args": list(args)})

    def _poll_frontend_requests(self) -> None:
        if self._request_poll_in_flight:
            return
        self._request_poll_in_flight = True
        events = self._frontend_events[:50]
        self._poll_event_count = len(events)
        encoded_events = json.dumps(events, ensure_ascii=False, separators=(",", ":"))
        self.page.runJavaScript(
            "(() => {"
            "const ready = typeof window.__ruralFindMeReceiveDesktopEvents === 'function';"
            f"if (ready) window.__ruralFindMeReceiveDesktopEvents({encoded_events});"
            "const commands = window.__ruralFindMeTakeDesktopCommands?.() ?? [];"
            "return JSON.stringify({ready, commands});"
            "})()",
            self._handle_frontend_exchange,
        )

    def _handle_frontend_exchange(self, payload: object) -> None:
        self._request_poll_in_flight = False
        exchange = parse_frontend_exchange(payload)
        if exchange is None:
            return
        ready, commands = exchange
        if ready and self._poll_event_count:
            del self._frontend_events[: self._poll_event_count]
        self._poll_event_count = 0
        for name, args in commands:
            self.bridge.handle_frontend_command(name, args)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.request_timer.stop()
        self.bridge.clear_sensitive_state()
        self.profile.clearHttpCache()
        self.profile.cookieStore().deleteAllCookies()
        self.view.setPage(None)
        event.accept()
