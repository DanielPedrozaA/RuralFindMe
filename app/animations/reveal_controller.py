from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class RevealController(QObject):
    message_changed = Signal(str)
    countdown_changed = Signal(str)
    completed = Signal()

    MESSAGES = [
        "Abriendo los documentos oficiales…",
        "Revisando las listas…",
        "Buscando tu número de identificación…",
        "Comprobando el resultado…",
    ]

    def __init__(self, reduced_animation: bool = False, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.reduced_animation = reduced_animation
        self._step = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self.stop()
        self._step = 0
        self.message_changed.emit(self.MESSAGES[0])
        self.countdown_changed.emit("")
        self._timer.start(250 if self.reduced_animation else 800)

    def stop(self) -> None:
        self._timer.stop()

    def skip(self) -> None:
        self.stop()
        self.countdown_changed.emit("")
        self.completed.emit()

    def _advance(self) -> None:
        self._step += 1
        if self._step < len(self.MESSAGES):
            self.message_changed.emit(self.MESSAGES[self._step])
            return
        countdown_index = self._step - len(self.MESSAGES)
        countdown = ["3", "2", "1"]
        if countdown_index < len(countdown):
            self.countdown_changed.emit(countdown[countdown_index])
            return
        self.stop()
        self.countdown_changed.emit("")
        self.completed.emit()
