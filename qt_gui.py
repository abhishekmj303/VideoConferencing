import cv2
import pyaudio
from PyQt6.QtCore import Qt, QThread, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, QDockWidget \
    , QLabel, QWidget, QListWidget, QListWidgetItem, QMessageBox \
    , QComboBox, QTextEdit, QLineEdit, QPushButton, QFileDialog, QDialog

import time

SAMPLE_RATE = 48000
BLOCK_SIZE = 256
CAMERA_RES = '240p'
frame_size = {
    '240p': [352, 240],
    '360p': [480, 360],
    '480p': [640, 480],
    '720p': [1080, 720],
    '1080p': [1920, 1080]
}
FRAME_WIDTH = frame_size[CAMERA_RES][0]
FRAME_HEIGHT = frame_size[CAMERA_RES][1]
NOCAM_FRAME = cv2.imread("nocam.jpeg")

ENABLE_AUDIO = False
pa = pyaudio.PyAudio()


class Microphone:
    def __init__(self):
        self.stream = pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=BLOCK_SIZE
        )

    def get_data(self):
        return self.stream.read(BLOCK_SIZE*2)


class AudioThread(QThread):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.stream = pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            output=True,
            frames_per_buffer=BLOCK_SIZE
        )

    def run(self):
        # if this is the current client, then don't play audio
        if self.client.microphone is not None:
            return
        while True:
            self.update_audio()

    def update_audio(self):
        data = self.client.get_audio()
        if data is not None:
            self.stream.write(data)


class Camera:
    def __init__(self):
        self.cap = cv2.VideoCapture(2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    def get_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT), interpolation=cv2.INTER_AREA)


class VideoWidget(QWidget):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_video)

        self.init_video()

    def init_ui(self):
        # self.resize(FRAME_WIDTH, FRAME_HEIGHT)
        self.video_viewer = QLabel()
        self.name_label = QLabel(self.client.name)
        self.video_viewer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.video_viewer)
        self.layout.addWidget(self.name_label)
        self.setLayout(self.layout)
    
    def init_video(self):
        self.timer.start(30)
    
    def update_video(self):
        frame = self.client.get_video()
        if frame is None:
            frame = NOCAM_FRAME
        # print(frame.shape)
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.video_viewer.setPixmap(QPixmap.fromImage(q_img))


class VideoListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_items = {}
        self.init_ui()

    def init_ui(self):
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)

    def add_client(self, client):
        video_widget = VideoWidget(client)

        item = QListWidgetItem()
        item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEnabled))
        self.addItem(item)
        # item.setSizeHint(video_widget.sizeHint())
        item.setSizeHint(QSize(FRAME_WIDTH, FRAME_HEIGHT))
        self.setItemWidget(item, video_widget)
        self.all_items[client.name] = item
    
    def remove_client(self, name: str):
        self.takeItem(self.row(self.all_items[name]))
        del self.all_items[name]


class ChatWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # self.resize(800, 600)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.clients_combo_box = QComboBox(self)
        # self.clients_combo_box.addItems(["Client 1", "Client 2", "Client 3"])
        self.layout.addWidget(self.clients_combo_box)

        self.central_widget = QTextEdit(self)
        self.central_widget.setReadOnly(True)
        self.layout.addWidget(self.central_widget)

        self.bottom_layout = QHBoxLayout()
        self.layout.addLayout(self.bottom_layout)

        self.line_edit = QLineEdit(self)
        self.bottom_layout.addWidget(self.line_edit)

        self.file_button = QPushButton("Select File", self)
        self.bottom_layout.addWidget(self.file_button)
        self.file_button.clicked.connect(self.select_file)

        self.send_button = QPushButton("Send", self)
        self.bottom_layout.addWidget(self.send_button)
        self.send_button.clicked.connect(self.send_text)
    
    def select_file(self):
        file_path = QFileDialog.getOpenFileName(None, "Select File", options= QFileDialog.Option.DontUseNativeDialog)[0]
        self.send_file(file_path)

    def send_text(self):
        text = self.line_edit.text()
        client_name = self.clients_combo_box.currentText()
        self.central_widget.append(f"You -> {client_name}: {text}")
        self.line_edit.clear()
    
    def send_file(self, file_path):
        file_name = file_path.split("/")[-1]
        client_name = self.clients_combo_box.currentText()
        self.central_widget.append(f"You -> {client_name}: {file_path}")


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Login")

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.name_label = QLabel("Username", self)
        self.layout.addWidget(self.name_label, 0, 0)

        self.name_edit = QLineEdit(self)
        self.layout.addWidget(self.name_edit, 0, 1)

        self.button = QPushButton("Login", self)
        self.layout.addWidget(self.button, 1, 1)

        self.button.clicked.connect(self.login)
    
    def get_name(self):
        return self.name_edit.text()
    
    def login(self):
        self.accept()
    
    def close(self):
        self.reject()

class MainWindow(QMainWindow):
    def __init__(self, client, server_conn):
        super().__init__()
        self.client = client
        self.server_conn = server_conn
        self.audio_threads = {}

        self.server_conn.add_client_signal.connect(self.add_client)
        self.server_conn.remove_client_signal.connect(self.remove_client)
        self.login_dialog = LoginDialog(self)
        if self.login_dialog.exec():
            self.server_conn.name = self.login_dialog.get_name()
            self.server_conn.start()
            self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Video Conferencing")
        self.setGeometry(0, 0, 1920, 1000)

        self.video_list_widget = VideoListWidget()
        self.setCentralWidget(self.video_list_widget)

        self.sidebar = QDockWidget("Chat", self)
        self.chat_widget = ChatWidget()
        self.sidebar.setWidget(self.chat_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.sidebar)

        # menus for camera and microphone toggle
        self.camera_menu = self.menuBar().addMenu("Camera")
        self.microphone_menu = self.menuBar().addMenu("Microphone")
        self.camera_menu.addAction("Disable Camera", self.toggle_camera)
        self.microphone_menu.addAction("Disable Microphone", self.toggle_microphone)
    
    def add_client(self, client):
        self.video_list_widget.add_client(client)
        if ENABLE_AUDIO:
            self.audio_threads[client.name] = AudioThread(client)
            self.audio_threads[client.name].start()
    
    def remove_client(self, name: str):
        self.video_list_widget.remove_client(name)
        if ENABLE_AUDIO:
            self.audio_threads[name].terminate()
            del self.audio_threads[name]

    def add_msg(self, name: str, msg: str):
        self.chat_widget.central_widget.append(f"{name} -> {self.client.name}: {msg}")
    
    def toggle_camera(self):
        if self.client.camera_enabled:
            self.camera_menu.actions()[0].setText("Enable Camera")
        else:
            self.camera_menu.actions()[0].setText("Disable Camera")
        self.client.camera_enabled = not self.client.camera_enabled

    def toggle_microphone(self):
        if self.client.microphone_enabled:
            self.microphone_menu.actions()[0].setText("Enable Microphone")
        else:
            self.microphone_menu.actions()[0].setText("Disable Microphone")
        self.client.microphone_enabled = not self.client.microphone_enabled
