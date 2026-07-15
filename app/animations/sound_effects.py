from PySide6.QtWidgets import QApplication


def play_reveal(enabled: bool) -> None:
    if enabled:
        QApplication.beep()
