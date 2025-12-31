import json
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView

APP_NAME = "Oldplayer"
DEFAULT_STATIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "stations.json"
USER_DATA_DIR = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME.lower()
USER_STATIONS_PATH = USER_DATA_DIR / "user_stations.json"


@dataclass
class Station:
    name: str
    genre: str
    stream_url: str


class StationModel(QtCore.QAbstractTableModel):
    headers = ["Name", "Genre", "Stream URL"]

    def __init__(self, stations):
        super().__init__()
        self._stations = stations

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._stations)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 3

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        station = self._stations[index.row()]
        if role in (QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole):
            if index.column() == 0:
                return station.name
            if index.column() == 1:
                return station.genre
            if index.column() == 2:
                return station.stream_url
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal:
            return self.headers[section]
        return str(section + 1)

    def flags(self, index):
        base = QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
        if index.column() == 2:
            return base | QtCore.Qt.ItemFlag.ItemIsEditable
        return base

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if role != QtCore.Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        station = self._stations[index.row()]
        if index.column() == 2:
            station.stream_url = value.strip()
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def add_station(self, station):
        self.beginInsertRows(QtCore.QModelIndex(), len(self._stations), len(self._stations))
        self._stations.append(station)
        self.endInsertRows()

    def remove_station(self, row):
        if row < 0 or row >= len(self._stations):
            return
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self._stations.pop(row)
        self.endRemoveRows()

    def stations(self):
        return self._stations


class OldplayerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 720)

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)

        self.video_player = QMediaPlayer(self)
        self.video_audio = QAudioOutput(self)
        self.video_player.setAudioOutput(self.video_audio)

        self.station_model = StationModel(self.load_stations())

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.build_radio_tab(), "Radio")
        self.tabs.addTab(self.build_video_tab(), "Video")
        self.tabs.addTab(self.build_twitch_tab(), "Twitch")
        self.setCentralWidget(self.tabs)

        self.apply_winamp_style()

    def apply_winamp_style(self):
        self.setStyleSheet(
            """
            QMainWindow { background-color: #0b0f0f; }
            QLabel, QLineEdit, QTableView, QTextEdit, QPushButton { color: #d9fdd3; }
            QTabWidget::pane { border: 1px solid #1b3b2f; }
            QTabBar::tab { background: #121a1a; padding: 8px; }
            QTabBar::tab:selected { background: #1b3b2f; }
            QTableView { background-color: #0f1717; gridline-color: #1b3b2f; }
            QPushButton { background-color: #1b3b2f; border: 1px solid #3d7d5e; padding: 6px 12px; }
            QPushButton:hover { background-color: #255042; }
            QLineEdit { background-color: #0f1717; border: 1px solid #3d7d5e; padding: 4px; }
            QGroupBox { border: 1px solid #1b3b2f; margin-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            """
        )

    def build_radio_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        header = QtWidgets.QLabel("Winamp-Style Radio Deck")
        header.setFont(QtGui.QFont("Arial", 16, QtGui.QFont.Weight.Bold))
        layout.addWidget(header)

        self.station_view = QtWidgets.QTableView()
        self.station_view.setModel(self.station_model)
        self.station_view.horizontalHeader().setStretchLastSection(True)
        self.station_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.station_view.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
            | QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked
        )
        layout.addWidget(self.station_view)

        controls = QtWidgets.QHBoxLayout()
        play_button = QtWidgets.QPushButton("Play")
        stop_button = QtWidgets.QPushButton("Stop")
        add_button = QtWidgets.QPushButton("Add Station")
        remove_button = QtWidgets.QPushButton("Remove Station")
        save_button = QtWidgets.QPushButton("Save Stations")
        controls.addWidget(play_button)
        controls.addWidget(stop_button)
        controls.addStretch(1)
        controls.addWidget(add_button)
        controls.addWidget(remove_button)
        controls.addWidget(save_button)
        layout.addLayout(controls)

        play_button.clicked.connect(self.play_selected_station)
        stop_button.clicked.connect(self.media_player.stop)
        add_button.clicked.connect(self.add_station_dialog)
        remove_button.clicked.connect(self.remove_station)
        save_button.clicked.connect(self.save_stations)

        footer = QtWidgets.QLabel(
            "Doppelklick auf die Stream-URL, um einen echten Stream einzutragen."
        )
        layout.addWidget(footer)

        return widget

    def build_video_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        header = QtWidgets.QLabel("Video Player")
        header.setFont(QtGui.QFont("Arial", 16, QtGui.QFont.Weight.Bold))
        layout.addWidget(header)

        self.video_widget = QVideoWidget()
        self.video_player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget, stretch=1)

        controls = QtWidgets.QHBoxLayout()
        open_button = QtWidgets.QPushButton("Open Video File")
        play_button = QtWidgets.QPushButton("Play")
        pause_button = QtWidgets.QPushButton("Pause")
        stop_button = QtWidgets.QPushButton("Stop")
        controls.addWidget(open_button)
        controls.addWidget(play_button)
        controls.addWidget(pause_button)
        controls.addWidget(stop_button)
        layout.addLayout(controls)

        open_button.clicked.connect(self.open_video_file)
        play_button.clicked.connect(self.video_player.play)
        pause_button.clicked.connect(self.video_player.pause)
        stop_button.clicked.connect(self.video_player.stop)

        return widget

    def build_twitch_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        header = QtWidgets.QLabel("Twitch / Web Video")
        header.setFont(QtGui.QFont("Arial", 16, QtGui.QFont.Weight.Bold))
        layout.addWidget(header)

        input_layout = QtWidgets.QHBoxLayout()
        self.twitch_url_input = QtWidgets.QLineEdit()
        self.twitch_url_input.setPlaceholderText("https://www.twitch.tv/<channel> oder Video-URL")
        load_button = QtWidgets.QPushButton("Load")
        input_layout.addWidget(self.twitch_url_input)
        input_layout.addWidget(load_button)
        layout.addLayout(input_layout)

        self.web_view = QWebEngineView()
        self.web_view.setUrl(QtCore.QUrl("https://www.twitch.tv"))
        layout.addWidget(self.web_view, stretch=1)

        load_button.clicked.connect(self.load_twitch_url)
        self.twitch_url_input.returnPressed.connect(self.load_twitch_url)

        return widget

    def play_selected_station(self):
        indexes = self.station_view.selectionModel().selectedRows()
        if not indexes:
            return
        station = self.station_model.stations()[indexes[0].row()]
        stream_url = station.stream_url
        if stream_url.startswith("radio-browser://"):
            stream_url = self.resolve_radio_browser_stream(stream_url)
            if stream_url:
                station.stream_url = stream_url
                self.station_model.dataChanged.emit(
                    self.station_model.index(indexes[0].row(), 2),
                    self.station_model.index(indexes[0].row(), 2),
                    [QtCore.Qt.ItemDataRole.DisplayRole],
                )
        if not stream_url:
            QtWidgets.QMessageBox.warning(
                self,
                "Stream URL fehlt",
                "Bitte trage eine Stream-URL für diesen Sender ein (Doppelklick auf die URL-Spalte).",
            )
            return
        self.media_player.setSource(QtCore.QUrl(stream_url))
        self.media_player.play()

    def add_station_dialog(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Add Station")
        layout = QtWidgets.QFormLayout(dialog)

        name_input = QtWidgets.QLineEdit()
        genre_input = QtWidgets.QLineEdit()
        url_input = QtWidgets.QLineEdit()
        layout.addRow("Name", name_input)
        layout.addRow("Genre", genre_input)
        layout.addRow("Stream URL", url_input)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            station = Station(
                name=name_input.text().strip() or "Custom Station",
                genre=genre_input.text().strip() or "Custom",
                stream_url=url_input.text().strip(),
            )
            self.station_model.add_station(station)

    def remove_station(self):
        indexes = self.station_view.selectionModel().selectedRows()
        if not indexes:
            return
        self.station_model.remove_station(indexes[0].row())

    def load_twitch_url(self):
        url = self.twitch_url_input.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = f"https://{url}"
        self.web_view.setUrl(QtCore.QUrl(url))

    def open_video_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Video",
            str(Path.home()),
            "Videos (*.mp4 *.mkv *.webm *.avi);;All Files (*.*)",
        )
        if not file_path:
            return
        self.video_player.setSource(QtCore.QUrl.fromLocalFile(file_path))
        self.video_player.play()

    def resolve_radio_browser_stream(self, stream_url):
        name = stream_url.replace("radio-browser://", "", 1).strip()
        if not name:
            return ""
        query = urllib.parse.quote(name)
        api_url = f"https://de1.api.radio-browser.info/json/stations/byname/{query}?limit=1"
        request = urllib.request.Request(api_url, headers={"User-Agent": APP_NAME})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            return ""
        if not data:
            return ""
        station = data[0]
        return station.get("url_resolved") or station.get("url") or ""

    def load_stations(self):
        stations = []
        if USER_STATIONS_PATH.exists():
            with USER_STATIONS_PATH.open("r", encoding="utf-8") as handle:
                stations.extend(json.load(handle))
        elif DEFAULT_STATIONS_PATH.exists():
            with DEFAULT_STATIONS_PATH.open("r", encoding="utf-8") as handle:
                stations.extend(json.load(handle))
        return [Station(**station) for station in stations]

    def save_stations(self):
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with USER_STATIONS_PATH.open("w", encoding="utf-8") as handle:
            json.dump(
                [station.__dict__ for station in self.station_model.stations()],
                handle,
                ensure_ascii=False,
                indent=2,
            )
        QtWidgets.QMessageBox.information(self, "Gespeichert", "Stationen wurden gespeichert.")


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = OldplayerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
