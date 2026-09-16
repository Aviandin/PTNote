import sys
import json
import importlib.util
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QSize, Signal
from PySide6.QtGui import QAction, QIcon, QFont, QColor
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QTextEdit,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QPushButton,
    QColorDialog,
    QSpinBox,
    QCheckBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QDialog,
    QFrame,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
NOTES_DIR = DATA_DIR / "notes"
PLUGINS_DIR = BASE_DIR / "plugins"

SETTINGS_FILE = DATA_DIR / "settings.json"

DATA_DIR.mkdir(exist_ok=True)
NOTES_DIR.mkdir(exist_ok=True)
PLUGINS_DIR.mkdir(exist_ok=True)


# ============================================================
# ASSETS
# ============================================================

CLOSE_ICON = ASSETS_DIR / "close.png"
COLOR_ICON = ASSETS_DIR / "color.png"
PIN_ICON = ASSETS_DIR / "pin.png"
OPTIONS_ICON = ASSETS_DIR / "options.png"
APP_ICON = ASSETS_DIR / "PTNote.ico"


def icon(path):
    if path.exists():
        return QIcon(str(path))
    return QIcon()


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {
    "default_note_color": "#fff7a8",
    "auto_pin": True,
    "auto_save": True,
    "remember_position": True,
    "remember_size": True,
    "default_text_size": 16,
    "enabled_plugins": [],
}


def load_settings():
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        settings = DEFAULT_SETTINGS.copy()
        settings.update(data)

        return settings

    except Exception as e:
        print(f"[PTNote] Could not load settings: {e}")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    try:
        DATA_DIR.mkdir(exist_ok=True)

        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)

    except Exception as e:
        print(f"[PTNote] Could not save settings: {e}")


# ============================================================
# COLOR HELPERS
# ============================================================

def readable_text_color(background):
    background = background.lstrip("#")

    try:
        r = int(background[0:2], 16)
        g = int(background[2:4], 16)
        b = int(background[4:6], 16)

        brightness = (
            r * 299 +
            g * 587 +
            b * 114
        ) / 1000

        if brightness < 150:
            return "#ffffff"

        return "#000000"

    except Exception:
        return "#000000"


# ============================================================
# TEXT EDITOR
# ============================================================

class NoteTextEdit(QTextEdit):

    spacePressed = Signal()

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_Space:

            # Insert the space first.
            super().keyPressEvent(event)

            # Save after the space has been inserted.
            self.spacePressed.emit()

            return

        super().keyPressEvent(event)


# ============================================================
# NOTE WINDOW
# ============================================================

class NoteWindow(QWidget):

    def __init__(
        self,
        app,
        note_id,
        title="Untitled Note",
        text="",
        color="#fff7a8",
        pinned=True,
        position=None,
        size=None,
        loading=False,
    ):
        super().__init__()

        self.app = app
        self.note_id = str(note_id)

        self.loading = loading

        self.note_color = color or "#fff7a8"
        self.pinned = bool(pinned)

        self.dragging = False
        self.drag_offset = QPoint()

        self.setWindowTitle(title or "Untitled Note")
        self.setWindowIcon(icon(APP_ICON))

        self.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True
        )

        self.setMinimumSize(250, 180)

        self.build_ui()

        # ----------------------------------------------------
        # Load title without triggering saves
        # ----------------------------------------------------

        self.title_edit.blockSignals(True)

        self.title_edit.setText(
            title or "Untitled Note"
        )

        self.title_edit.blockSignals(False)

        # ----------------------------------------------------
        # Load content without triggering saves
        # ----------------------------------------------------

        self.editor.blockSignals(True)

        self.editor.setPlainText(
            text or ""
        )

        self.editor.blockSignals(False)

        # ----------------------------------------------------
        # Font
        # ----------------------------------------------------

        self.editor.setFont(
            QFont(
                "Arial",
                int(
                    self.app.settings.get(
                        "default_text_size",
                        16
                    )
                )
            )
        )

        self.apply_color()

        self.apply_pin()

        # ----------------------------------------------------
        # Restore size
        # ----------------------------------------------------

        if (
            self.app.settings.get(
                "remember_size",
                True
            )
            and size
            and len(size) == 2
        ):

            try:

                width = max(
                    250,
                    int(size[0])
                )

                height = max(
                    180,
                    int(size[1])
                )

                self.resize(
                    width,
                    height
                )

            except Exception:

                self.resize(
                    420,
                    300
                )

        else:

            self.resize(
                420,
                300
            )

        # ----------------------------------------------------
        # Restore position
        # ----------------------------------------------------

        if (
            self.app.settings.get(
                "remember_position",
                True
            )
            and position
            and len(position) == 2
        ):

            try:

                self.move(
                    int(position[0]),
                    int(position[1])
                )

            except Exception:

                self.move(
                    100 + len(
                        self.app.open_notes
                    ) * 30,
                    100 + len(
                        self.app.open_notes
                    ) * 30
                )

        else:

            self.move(
                100 + len(
                    self.app.open_notes
                ) * 30,
                100 + len(
                    self.app.open_notes
                ) * 30
            )

        # ----------------------------------------------------
        # Connect signals AFTER loading
        # ----------------------------------------------------

        self.title_edit.textChanged.connect(
            self.title_changed
        )

        self.editor.textChanged.connect(
            self.content_changed
        )

        self.editor.spacePressed.connect(
            self.space_save
        )

        self.loading = False

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        self.setObjectName(
            "NoteWindow"
        )

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        main_layout.setSpacing(0)

        # ----------------------------------------------------
        # Custom header
        # ----------------------------------------------------

        header = QFrame()

        header.setFixedHeight(42)

        header_layout = QHBoxLayout(
            header
        )

        header_layout.setContentsMargins(
            6,
            4,
            6,
            4
        )

        header_layout.setSpacing(5)

        # ----------------------------------------------------
        # Close
        # ----------------------------------------------------

        self.close_button = QPushButton()

        self.close_button.setIcon(
            icon(CLOSE_ICON)
        )

        self.close_button.setIconSize(
            QSize(22, 22)
        )

        self.close_button.setFixedSize(
            32,
            32
        )

        self.close_button.setToolTip(
            "Close note"
        )

        self.close_button.clicked.connect(
            self.close
        )

        # ----------------------------------------------------
        # Color
        # ----------------------------------------------------

        self.color_button = QPushButton()

        self.color_button.setIcon(
            icon(COLOR_ICON)
        )

        self.color_button.setIconSize(
            QSize(22, 22)
        )

        self.color_button.setFixedSize(
            32,
            32
        )

        self.color_button.setToolTip(
            "Change note color"
        )

        self.color_button.clicked.connect(
            self.choose_color
        )

        # ----------------------------------------------------
        # Pin
        # ----------------------------------------------------

        self.pin_button = QPushButton()

        self.pin_button.setIcon(
            icon(PIN_ICON)
        )

        self.pin_button.setIconSize(
            QSize(22, 22)
        )

        self.pin_button.setFixedSize(
            32,
            32
        )

        self.pin_button.setToolTip(
            "Toggle always on top"
        )

        self.pin_button.clicked.connect(
            self.toggle_pin
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        self.title_edit = QLineEdit()

        self.title_edit.setPlaceholderText(
            "Untitled Note"
        )

        self.title_edit.setFrame(
            False
        )

        self.title_edit.setFont(
            QFont(
                "Arial",
                11,
                QFont.Weight.Bold
            )
        )

        header_layout.addWidget(
            self.close_button
        )

        header_layout.addWidget(
            self.color_button
        )

        header_layout.addWidget(
            self.pin_button
        )

        header_layout.addSpacing(5)

        header_layout.addWidget(
            self.title_edit,
            1
        )

        # ----------------------------------------------------
        # Editor
        # ----------------------------------------------------

        self.editor = NoteTextEdit()

        self.editor.setFont(
            QFont(
                "Arial",
                int(
                    self.app.settings.get(
                        "default_text_size",
                        16
                    )
                )
            )
        )

        self.editor.setAcceptRichText(
            False
        )

        self.editor.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.editor.setContentsMargins(
            8,
            8,
            8,
            8
        )

        main_layout.addWidget(
            header
        )

        main_layout.addWidget(
            self.editor,
            1
        )

        self.header = header

    # ========================================================
    # COLOR
    # ========================================================

    def choose_color(self):

        color = QColorDialog.getColor(
            QColor(self.note_color),
            self,
            "Choose Note Color"
        )

        if not color.isValid():
            return

        self.note_color = color.name()

        self.apply_color()

        self.save_note()

    def apply_color(self):

        text_color = readable_text_color(
            self.note_color
        )

        self.setStyleSheet(
            f"""
            QWidget#NoteWindow {{
                background: {self.note_color};
                border: none;
            }}

            QFrame {{
                background: {self.note_color};
                border: none;
            }}

            QTextEdit {{
                background: {self.note_color};
                color: {text_color};
                border: none;
                selection-background-color:
                    rgba(80,80,80,100);
            }}

            QLineEdit {{
                background: transparent;
                color: {text_color};
                border: none;
            }}

            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}

            QPushButton:hover {{
                background: rgba(128,128,128,45);
            }}
            """
        )

    # ========================================================
    # PIN
    # ========================================================

    def toggle_pin(self):

        self.pinned = not self.pinned

        self.apply_pin()

        self.save_note()

    def apply_pin(self):

        # ----------------------------------------------------
        # BORDERLESS WINDOW
        # ----------------------------------------------------

        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
        )

        if self.pinned:

            flags |= (
                Qt.WindowType.WindowStaysOnTopHint
            )

        self.setWindowFlags(
            flags
        )

        # Changing window flags can hide
        # the window, so show it again.
        if self.isVisible():

            self.show()

        if self.pinned:

            self.pin_button.setToolTip(
                "Always on top: ON"
            )

        else:

            self.pin_button.setToolTip(
                "Always on top: OFF"
            )

    # ========================================================
    # TITLE
    # ========================================================

    def get_note_title(self):

        title = (
            self.title_edit
            .text()
            .strip()
        )

        if not title:

            return "Untitled Note"

        return title

    def title_changed(self):

        self.setWindowTitle(
            self.get_note_title()
        )

        self.app.refresh_tray_menu()

        if (
            not self.loading
            and self.app.settings.get(
                "auto_save",
                True
            )
        ):

            self.save_note()

    # ========================================================
    # CONTENT
    # ========================================================

    def content_changed(self):

        if (
            not self.loading
            and self.app.settings.get(
                "auto_save",
                True
            )
        ):

            self.save_note()

    # ========================================================
    # SPACE SAVE
    # ========================================================

    def space_save(self):

        self.save_note()

    # ========================================================
    # SAVE NOTE
    # ========================================================

    def save_note(self):

        try:

            NOTES_DIR.mkdir(
                parents=True,
                exist_ok=True
            )

            data = {
                "id": self.note_id,

                "title": self.get_note_title(),

                "text": self.editor.toPlainText(),

                "color": self.note_color,

                "pinned": self.pinned,

                "position": [
                    self.x(),
                    self.y()
                ],

                "size": [
                    self.width(),
                    self.height()
                ],
            }

            file_path = (
                NOTES_DIR
                / f"{self.note_id}.json"
            )

            with open(
                file_path,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    data,
                    f,
                    indent=4,
                    ensure_ascii=False
                )

            print(
                f"[PTNote] Saved: {file_path}"
            )

            self.app.refresh_tray_menu()

        except Exception as e:

            print(
                f"[PTNote] ERROR saving "
                f"{self.note_id}: {e}"
            )

    # ========================================================
    # CLOSE NOTE
    # ========================================================

    def closeEvent(self, event):

        # Save before closing.
        self.save_note()

        # IMPORTANT:
        # The JSON file remains.
        #
        # Closing the window only removes the
        # window from the currently-open notes.
        #
        # The note can be reopened from:
        #
        # PTNote -> Notes -> Note Name

        self.app.note_window_closed(
            self.note_id
        )

        event.accept()

    # ========================================================
    # BRING TO FRONT
    # ========================================================

    def bring_to_front(self):

        if not self.isVisible():

            self.show()

        self.raise_()

        self.activateWindow()

    # ========================================================
    # DRAGGING
    # ========================================================

    def mousePressEvent(self, event):

        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):

            # Only drag from the custom header.
            if event.position().y() <= 42:

                self.dragging = True

                self.drag_offset = (
                    event.globalPosition()
                    .toPoint()
                    - self.frameGeometry()
                    .topLeft()
                )

                event.accept()

                return

        super().mousePressEvent(
            event
        )

    def mouseMoveEvent(self, event):

        if (
            self.dragging
            and event.buttons()
            & Qt.MouseButton.LeftButton
        ):

            self.move(
                event.globalPosition()
                .toPoint()
                - self.drag_offset
            )

            return

        super().mouseMoveEvent(
            event
        )

    def mouseReleaseEvent(self, event):

        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):

            if self.dragging:

                self.dragging = False

                if self.app.settings.get(
                    "auto_save",
                    True
                ):

                    self.save_note()

        super().mouseReleaseEvent(
            event
        )


# ============================================================
# SETTINGS WINDOW
# ============================================================

class SettingsWindow(QDialog):

    def __init__(self, app):

        super().__init__()

        self.app = app

        self.setWindowTitle(
            "PTNote Options"
        )

        self.setWindowIcon(
            icon(APP_ICON)
        )

        self.setMinimumWidth(
            400
        )

        layout = QVBoxLayout(
            self
        )

        # ----------------------------------------------------
        # Default color
        # ----------------------------------------------------

        color_layout = QHBoxLayout()

        color_layout.addWidget(
            QLabel(
                "Default note color:"
            )
        )

        self.color_button = QPushButton(
            self.app.settings.get(
                "default_note_color",
                "#fff7a8"
            )
        )

        self.color_button.clicked.connect(
            self.choose_default_color
        )

        color_layout.addWidget(
            self.color_button,
            1
        )

        layout.addLayout(
            color_layout
        )

        # ----------------------------------------------------
        # Auto pin
        # ----------------------------------------------------

        self.auto_pin = QCheckBox(
            "Automatically pin new notes"
        )

        self.auto_pin.setChecked(
            self.app.settings.get(
                "auto_pin",
                True
            )
        )

        layout.addWidget(
            self.auto_pin
        )

        # ----------------------------------------------------
        # Auto save
        # ----------------------------------------------------

        self.auto_save = QCheckBox(
            "Automatically save notes"
        )

        self.auto_save.setChecked(
            self.app.settings.get(
                "auto_save",
                True
            )
        )

        layout.addWidget(
            self.auto_save
        )

        # ----------------------------------------------------
        # Remember position
        # ----------------------------------------------------

        self.remember_position = QCheckBox(
            "Remember note position"
        )

        self.remember_position.setChecked(
            self.app.settings.get(
                "remember_position",
                True
            )
        )

        layout.addWidget(
            self.remember_position
        )

        # ----------------------------------------------------
        # Remember size
        # ----------------------------------------------------

        self.remember_size = QCheckBox(
            "Remember note size"
        )

        self.remember_size.setChecked(
            self.app.settings.get(
                "remember_size",
                True
            )
        )

        layout.addWidget(
            self.remember_size
        )

        # ----------------------------------------------------
        # Text size
        # ----------------------------------------------------

        text_size_layout = QHBoxLayout()

        text_size_layout.addWidget(
            QLabel(
                "Default text size:"
            )
        )

        self.text_size = QSpinBox()

        self.text_size.setMinimum(
            6
        )

        self.text_size.setMaximum(
            72
        )

        self.text_size.setValue(
            int(
                self.app.settings.get(
                    "default_text_size",
                    16
                )
            )
        )

        text_size_layout.addWidget(
            self.text_size
        )

        layout.addLayout(
            text_size_layout
        )

        # ----------------------------------------------------
        # Plugins
        # ----------------------------------------------------

        self.plugins_button = QPushButton(
            "Manage Plugins..."
        )

        self.plugins_button.clicked.connect(
            self.open_plugins
        )

        layout.addWidget(
            self.plugins_button
        )

        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        buttons = QHBoxLayout()

        buttons.addStretch()

        cancel = QPushButton(
            "Cancel"
        )

        cancel.clicked.connect(
            self.reject
        )

        save = QPushButton(
            "Save"
        )

        save.clicked.connect(
            self.save
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            save
        )

        layout.addLayout(
            buttons
        )

    def choose_default_color(self):

        current = self.app.settings.get(
            "default_note_color",
            "#fff7a8"
        )

        color = QColorDialog.getColor(
            QColor(current),
            self,
            "Choose Default Note Color"
        )

        if color.isValid():

            self.color_button.setText(
                color.name()
            )

    def open_plugins(self):

        window = PluginsWindow(
            self.app,
            self
        )

        window.exec()

    def save(self):

        self.app.settings[
            "default_note_color"
        ] = self.color_button.text()

        self.app.settings[
            "auto_pin"
        ] = self.auto_pin.isChecked()

        self.app.settings[
            "auto_save"
        ] = self.auto_save.isChecked()

        self.app.settings[
            "remember_position"
        ] = (
            self.remember_position
            .isChecked()
        )

        self.app.settings[
            "remember_size"
        ] = (
            self.remember_size
            .isChecked()
        )

        self.app.settings[
            "default_text_size"
        ] = self.text_size.value()

        save_settings(
            self.app.settings
        )

        self.accept()


# ============================================================
# PLUGINS WINDOW
# ============================================================

class PluginsWindow(QDialog):

    def __init__(
        self,
        app,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.app = app

        self.setWindowTitle(
            "PTNote Plugins"
        )

        self.setWindowIcon(
            icon(APP_ICON)
        )

        self.resize(
            650,
            450
        )

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            "Plugins"
        )

        title.setFont(
            QFont(
                "Arial",
                16,
                QFont.Weight.Bold
            )
        )

        layout.addWidget(
            title
        )

        columns = QHBoxLayout()

        # ----------------------------------------------------
        # Disabled
        # ----------------------------------------------------

        disabled_layout = QVBoxLayout()

        disabled_layout.addWidget(
            QLabel(
                "Disabled"
            )
        )

        self.disabled_list = QListWidget()

        disabled_layout.addWidget(
            self.disabled_list
        )

        columns.addLayout(
            disabled_layout
        )

        # ----------------------------------------------------
        # Enable / Disable
        # ----------------------------------------------------

        button_layout = QVBoxLayout()

        button_layout.addStretch()

        enable_button = QPushButton(
            "Enable →"
        )

        enable_button.clicked.connect(
            self.enable_selected
        )

        disable_button = QPushButton(
            "← Disable"
        )

        disable_button.clicked.connect(
            self.disable_selected
        )

        button_layout.addWidget(
            enable_button
        )

        button_layout.addWidget(
            disable_button
        )

        button_layout.addStretch()

        columns.addLayout(
            button_layout
        )

        # ----------------------------------------------------
        # Enabled
        # ----------------------------------------------------

        enabled_layout = QVBoxLayout()

        enabled_layout.addWidget(
            QLabel(
                "Enabled"
            )
        )

        self.enabled_list = QListWidget()

        enabled_layout.addWidget(
            self.enabled_list
        )

        columns.addLayout(
            enabled_layout
        )

        layout.addLayout(
            columns
        )

        # ----------------------------------------------------
        # Information
        # ----------------------------------------------------

        self.info_label = QLabel(
            "Select a plugin to view information."
        )

        self.info_label.setWordWrap(
            True
        )

        layout.addWidget(
            self.info_label
        )

        self.disabled_list.currentItemChanged.connect(
            self.show_plugin_info
        )

        self.enabled_list.currentItemChanged.connect(
            self.show_plugin_info
        )

        self.plugins = (
            self.app.load_plugins()
        )

        self.refresh_lists()

    def refresh_lists(self):

        self.disabled_list.clear()
        self.enabled_list.clear()

        enabled = set(
            self.app.settings.get(
                "enabled_plugins",
                []
            )
        )

        for plugin in self.plugins:

            if (
                plugin["filename"]
                in enabled
            ):

                self.enabled_list.addItem(
                    plugin["name"]
                )

            else:

                self.disabled_list.addItem(
                    plugin["name"]
                )

    def find_plugin_by_name(
        self,
        name
    ):

        for plugin in self.plugins:

            if plugin["name"] == name:

                return plugin

        return None

    def show_plugin_info(
        self,
        current,
        previous
    ):

        if current is None:
            return

        plugin = (
            self.find_plugin_by_name(
                current.text()
            )
        )

        if plugin is None:
            return

        self.info_label.setText(
            f"Plugin: {plugin['name']}\n"
            f"Author: {plugin['author']}\n"
            f"File: {plugin['filename']}"
        )

    def enable_selected(self):

        item = (
            self.disabled_list
            .currentItem()
        )

        if item is None:
            return

        plugin = (
            self.find_plugin_by_name(
                item.text()
            )
        )

        if plugin is None:
            return

        enabled = (
            self.app.settings
            .setdefault(
                "enabled_plugins",
                []
            )
        )

        if (
            plugin["filename"]
            not in enabled
        ):

            enabled.append(
                plugin["filename"]
            )

        save_settings(
            self.app.settings
        )

        self.refresh_lists()

    def disable_selected(self):

        item = (
            self.enabled_list
            .currentItem()
        )

        if item is None:
            return

        plugin = (
            self.find_plugin_by_name(
                item.text()
            )
        )

        if plugin is None:
            return

        enabled = (
            self.app.settings
            .setdefault(
                "enabled_plugins",
                []
            )
        )

        if (
            plugin["filename"]
            in enabled
        ):

            enabled.remove(
                plugin["filename"]
            )

        save_settings(
            self.app.settings
        )

        self.refresh_lists()


# ============================================================
# PTNOTE APPLICATION
# ============================================================

class PTNoteApp:

    def __init__(
        self,
        qt_app
    ):

        self.qt_app = qt_app

        self.settings = (
            load_settings()
        )

        # Only currently-open windows.
        self.open_notes = {}

        self.tray = QSystemTrayIcon(
            icon(APP_ICON),
            self.qt_app
        )

        self.tray.setToolTip(
            "PTNote"
        )

        self.tray.activated.connect(
            self.tray_activated
        )

        self.refresh_tray_menu()

        self.tray.show()

        # Load saved notes.
        self.load_saved_notes()

        # Refresh menu after loading.
        self.refresh_tray_menu()

        # Load plugin metadata.
        self.plugins = (
            self.load_plugins()
        )

    # ========================================================
    # NEXT NOTE ID
    # ========================================================

    def get_next_note_id(self):

        highest = 0

        for file in NOTES_DIR.glob(
            "note_*.json"
        ):

            try:

                number = int(
                    file.stem.split(
                        "_"
                    )[1]
                )

                highest = max(
                    highest,
                    number
                )

            except Exception:
                pass

        return (
            f"note_{highest + 1}"
        )

    # ========================================================
    # GET SAVED NOTES
    # ========================================================

    def get_saved_notes(self):

        saved = []

        NOTES_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        for file_path in sorted(
            NOTES_DIR.glob("*.json")
        ):

            try:

                with open(
                    file_path,
                    "r",
                    encoding="utf-8"
                ) as f:

                    data = json.load(f)

                # ------------------------------------------------
                # List format
                # ------------------------------------------------

                if isinstance(
                    data,
                    list
                ):

                    for entry in data:

                        if isinstance(
                            entry,
                            dict
                        ):

                            saved.append(
                                self.normalize_note(
                                    entry,
                                    file_path
                                )
                            )

                # ------------------------------------------------
                # Dictionary format
                # ------------------------------------------------

                elif isinstance(
                    data,
                    dict
                ):

                    if (
                        "title" in data
                        or "text" in data
                        or "content" in data
                    ):

                        saved.append(
                            self.normalize_note(
                                data,
                                file_path
                            )
                        )

                    elif isinstance(
                        data.get("notes"),
                        list
                    ):

                        for entry in data[
                            "notes"
                        ]:

                            if isinstance(
                                entry,
                                dict
                            ):

                                saved.append(
                                    self.normalize_note(
                                        entry,
                                        file_path
                                    )
                                )

            except Exception as e:

                print(
                    f"[PTNote] ERROR reading "
                    f"{file_path.name}: {e}"
                )

        return saved

    # ========================================================
    # NORMALIZE NOTE
    # ========================================================

    def normalize_note(
        self,
        data,
        file_path
    ):

        note_id = data.get(
            "id",
            file_path.stem
        )

        title = data.get(
            "title",
            data.get(
                "name",
                "Untitled Note"
            )
        )

        text = data.get(
            "text",
            data.get(
                "content",
                ""
            )
        )

        color = data.get(
            "color",
            self.settings.get(
                "default_note_color",
                "#fff7a8"
            )
        )

        pinned = data.get(
            "pinned",
            self.settings.get(
                "auto_pin",
                True
            )
        )

        position = data.get(
            "position",
            None
        )

        size = data.get(
            "size",
            None
        )

        return {
            "id": str(note_id),
            "title": str(title),
            "text": str(text),
            "color": str(color),
            "pinned": bool(pinned),
            "position": position,
            "size": size,
            "file": file_path,
        }

    # ========================================================
    # LOAD SAVED NOTES
    # ========================================================

    def load_saved_notes(self):

        print("=" * 40)

        print(
            "[PTNote] Loading saved notes..."
        )

        print(
            "[PTNote] Notes folder:"
        )

        print(
            f"         {NOTES_DIR}"
        )

        print("=" * 40)

        saved_notes = (
            self.get_saved_notes()
        )

        loaded = 0

        for data in saved_notes:

            note_id = data["id"]

            print(
                f"[PTNote] Found: "
                f"{data['file'].name}"
            )

            print(
                f"[PTNote] Loaded: "
                f"{data['title']}"
            )

            if note_id in self.open_notes:

                continue

            note = NoteWindow(
                self,
                note_id=note_id,
                title=data["title"],
                text=data["text"],
                color=data["color"],
                pinned=data["pinned"],
                position=data["position"],
                size=data["size"],
                loading=True,
            )

            self.open_notes[
                note_id
            ] = note

            loaded += 1

            note.show()

        print("=" * 40)

        print(
            f"[PTNote] Loaded "
            f"{loaded} saved note(s)."
        )

        print("=" * 40)

    # ========================================================
    # OPEN SAVED NOTE
    # ========================================================

    def open_saved_note(
        self,
        note_id
    ):

        note_id = str(
            note_id
        )

        # ----------------------------------------------------
        # Already open
        # ----------------------------------------------------

        if note_id in self.open_notes:

            note = (
                self.open_notes[
                    note_id
                ]
            )

            note.bring_to_front()

            return

        # ----------------------------------------------------
        # Find JSON
        # ----------------------------------------------------

        file_path = (
            NOTES_DIR
            / f"{note_id}.json"
        )

        if not file_path.exists():

            print(
                f"[PTNote] Could not find "
                f"{file_path}"
            )

            return

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as f:

                raw = json.load(f)

            data = self.normalize_note(
                raw,
                file_path
            )

            note = NoteWindow(
                self,
                note_id=data["id"],
                title=data["title"],
                text=data["text"],
                color=data["color"],
                pinned=data["pinned"],
                position=data["position"],
                size=data["size"],
                loading=True,
            )

            self.open_notes[
                note_id
            ] = note

            note.show()

            note.bring_to_front()

            self.refresh_tray_menu()

            print(
                f"[PTNote] Opened saved note: "
                f"{data['title']}"
            )

        except Exception as e:

            print(
                f"[PTNote] ERROR opening "
                f"{file_path.name}: {e}"
            )

            QMessageBox.warning(
                None,
                "PTNote",
                f"Could not open note:\n\n{e}"
            )

    # ========================================================
    # NEW NOTE
    # ========================================================

    def new_note(self):

        note_id = (
            self.get_next_note_id()
        )

        note = NoteWindow(
            self,
            note_id=note_id,
            title="Untitled Note",
            text="",
            color=self.settings.get(
                "default_note_color",
                "#fff7a8"
            ),
            pinned=self.settings.get(
                "auto_pin",
                True
            ),
            position=None,
            size=None,
            loading=False,
        )

        self.open_notes[
            note_id
        ] = note

        note.show()

        # Create the permanent JSON immediately.
        note.save_note()

        self.refresh_tray_menu()

        note.title_edit.setFocus()

        print(
            f"[PTNote] Created new note: "
            f"{note_id}.json"
        )

    # ========================================================
    # NOTE WINDOW CLOSED
    # ========================================================

    def note_window_closed(
        self,
        note_id
    ):

        note_id = str(
            note_id
        )

        if note_id in self.open_notes:

            del self.open_notes[
                note_id
            ]

        # DO NOT DELETE THE JSON FILE.

        self.refresh_tray_menu()

    # ========================================================
    # TRAY MENU
    # ========================================================

    def refresh_tray_menu(self):

        menu = QMenu()

        # ----------------------------------------------------
        # New Note
        # ----------------------------------------------------

        new_action = QAction(
            "New Note",
            menu
        )

        new_action.triggered.connect(
            self.new_note
        )

        menu.addAction(
            new_action
        )

        # ----------------------------------------------------
        # Notes
        # ----------------------------------------------------

        notes_menu = QMenu(
            "Notes",
            menu
        )

        saved_notes = (
            self.get_saved_notes()
        )

        saved_notes.sort(
            key=lambda x:
            x["title"].lower()
        )

        if not saved_notes:

            empty_action = QAction(
                "No saved notes",
                notes_menu
            )

            empty_action.setEnabled(
                False
            )

            notes_menu.addAction(
                empty_action
            )

        else:

            for data in saved_notes:

                note_action = QAction(
                    data["title"],
                    notes_menu
                )

                note_id = data["id"]

                note_action.triggered.connect(
                    lambda checked=False,
                    nid=note_id:
                    self.open_saved_note(
                        nid
                    )
                )

                notes_menu.addAction(
                    note_action
                )

        menu.addMenu(
            notes_menu
        )

        # ----------------------------------------------------
        # Separator
        # ----------------------------------------------------

        menu.addSeparator()

        # ----------------------------------------------------
        # Options
        # ----------------------------------------------------

        options_action = QAction(
            icon(OPTIONS_ICON),
            "Options",
            menu
        )

        options_action.triggered.connect(
            self.show_options
        )

        menu.addAction(
            options_action
        )

        # ----------------------------------------------------
        # Exit
        # ----------------------------------------------------

        menu.addSeparator()

        exit_action = QAction(
            "Exit PTNote",
            menu
        )

        exit_action.triggered.connect(
            self.exit
        )

        menu.addAction(
            exit_action
        )

        self.tray.setContextMenu(
            menu
        )

    # ========================================================
    # OPTIONS
    # ========================================================

    def show_options(self):

        window = SettingsWindow(
            self
        )

        window.exec()

        self.refresh_tray_menu()

    # ========================================================
    # TRAY ACTIVATION
    # ========================================================

    def tray_activated(
        self,
        reason
    ):

        if (
            reason
            == QSystemTrayIcon
            .ActivationReason
            .DoubleClick
        ):

            self.new_note()

    # ========================================================
    # PLUGIN LOADING
    # ========================================================

    def load_plugins(self):

        plugins = []

        PLUGINS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        for file_path in sorted(
            PLUGINS_DIR.glob("*.py")
        ):

            if file_path.name.startswith(
                "_"
            ):

                continue

            try:

                module_name = (
                    "ptnote_plugin_"
                    + file_path.stem
                )

                spec = (
                    importlib.util
                    .spec_from_file_location(
                        module_name,
                        file_path
                    )
                )

                if spec is None:
                    continue

                module = (
                    importlib.util
                    .module_from_spec(
                        spec
                    )
                )

                spec.loader.exec_module(
                    module
                )

                plugin_name = getattr(
                    module,
                    "PLUGIN_NAME",
                    file_path.stem
                )

                author = getattr(
                    module,
                    "AUTHOR",
                    "Unknown"
                )

                run_function = getattr(
                    module,
                    "run",
                    None
                )

                plugins.append(
                    {
                        "name":
                            str(plugin_name),

                        "author":
                            str(author),

                        "filename":
                            file_path.name,

                        "module":
                            module,

                        "run":
                            run_function,
                    }
                )

            except Exception as e:

                print(
                    f"[PTNote] Plugin error "
                    f"{file_path.name}: {e}"
                )

        return plugins

    # ========================================================
    # EXIT
    # ========================================================

    def exit(self):

        # Save every currently-open note.
        for note in list(
            self.open_notes.values()
        ):

            try:

                note.save_note()

            except Exception:
                pass

        self.tray.hide()

        self.qt_app.quit()


# ============================================================
# MAIN
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    # Keep PTNote running when all note
    # windows are closed.
    app.setQuitOnLastWindowClosed(
        False
    )

    if APP_ICON.exists():

        app.setWindowIcon(
            icon(APP_ICON)
        )

    ptnote = PTNoteApp(
        app
    )

    # Keep a reference alive.
    app.ptnote = ptnote

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":

    main()