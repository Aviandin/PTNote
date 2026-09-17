PLUGIN_NAME = "100 Word Sound"
AUTHOR = "Aviandin"

"""
PTNote plugin: plays a short Windows sound every 100 words typed.

No extra packages or sound files are required. The plugin uses Windows'
built-in winsound module.

The plugin is self-contained and does not require changes to PTNote's main.py.
It checks PTNote's settings.json and only activates when this plugin's filename
is present in enabled_plugins. Restart PTNote after enabling/disabling it.
"""

import os
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QApplication, QTextEdit, QPlainTextEdit

try:
    import winsound
except ImportError:
    winsound = None

_PLUGIN_FILENAME = Path(__file__).name
_WORDS_PER_SOUND = 100
_FILTER = None
_LAST_COUNTS = {}


def _settings_path():
    """Find PTNote's settings.json without depending on PTNote internals."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        path = Path(appdata) / "PTNote" / "settings.json"
        if path.exists():
            return path

    # Development/source version fallback.
    return Path(__file__).resolve().parent.parent / "data" / "settings.json"


def _is_enabled():
    try:
        import json
        path = _settings_path()
        if not path.exists():
            return False
        with path.open("r", encoding="utf-8") as f:
            settings = json.load(f)
        enabled = settings.get("enabled_plugins", [])
        return _PLUGIN_FILENAME in enabled
    except Exception:
        return False


def _word_count(text):
    # Count whitespace-separated words. This is deliberately simple and
    # matches normal typing in a note well.
    return len(text.split())


def _play_sound():
    if winsound is None:
        return

    # Run the Windows sound call off the UI thread so typing never waits on it.
    def play():
        try:
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            try:
                winsound.Beep(880, 120)
            except Exception:
                pass

    threading.Thread(target=play, daemon=True).start()


class _WordSoundFilter(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ChildAdded:
            # New note text widgets will be caught by QApplication events too.
            pass

        if event.type() == QEvent.Type.KeyPress:
            # The actual text is checked after Qt processes the key, so spaces,
            # pasted text, and other edits are handled consistently.
            QApplication.instance().processEvents()
            self._check_widget(watched)

        elif event.type() in (
            QEvent.Type.Paste,
            QEvent.Type.InputMethod,
        ):
            QApplication.instance().processEvents()
            self._check_widget(watched)

        return False

    def _check_widget(self, widget):
        if not isinstance(widget, (QTextEdit, QPlainTextEdit)):
            return

        try:
            text = widget.toPlainText()
        except Exception:
            return

        key = id(widget)
        count = _word_count(text)
        previous = _LAST_COUNTS.get(key, 0)

        # Play once when crossing 100, 200, 300, etc.
        if count >= _WORDS_PER_SOUND and count // _WORDS_PER_SOUND > previous // _WORDS_PER_SOUND:
            _play_sound()

        _LAST_COUNTS[key] = count



def _install():
    global _FILTER

    if winsound is None or not _is_enabled():
        return

    app = QApplication.instance()
    if app is None:
        return

    if _FILTER is None:
        _FILTER = _WordSoundFilter(app)
        app.installEventFilter(_FILTER)


def run(ptnote):
    """Plugin entry point for PTNote's plugin system."""
    _install()


# PTNote currently discovers plugin modules by importing them. Schedule the
# installation after the Qt event loop starts, while still respecting the
# enabled_plugins setting. This keeps the feature entirely inside the plugin.
try:
    app = QApplication.instance()
    if app is not None:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, _install)
except Exception:
    pass
