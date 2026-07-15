from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class ConfettiWidget(QWidget):
    COLORS = ["#F8C537", "#FF6B6B", "#39C6B4", "#6C63FF", "#45A3FF"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._pieces: list[dict] = []
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self, count: int = 85) -> None:
        width = max(self.width(), 800)
        self._pieces = [
            {
                "p": QPointF(random.uniform(0, width), random.uniform(-400, -10)),
                "vy": random.uniform(4, 10),
                "vx": random.uniform(-1.2, 1.2),
                "size": random.uniform(5, 10),
                "color": QColor(random.choice(self.COLORS)),
            }
            for _ in range(count)
        ]
        self.show()
        self.raise_()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._pieces.clear()
        self.hide()

    def _tick(self) -> None:
        alive = False
        for piece in self._pieces:
            point: QPointF = piece["p"]
            point.setX(point.x() + piece["vx"])
            point.setY(point.y() + piece["vy"])
            if point.y() < self.height() + 20:
                alive = True
        self.update()
        if not alive:
            self.stop()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for piece in self._pieces:
            painter.setBrush(piece["color"])
            painter.setPen(Qt.PenStyle.NoPen)
            point: QPointF = piece["p"]
            size = piece["size"]
            painter.drawRoundedRect(point.x(), point.y(), size, size * 0.55, 2, 2)
