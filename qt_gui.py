import os
import cv2
import pyaudio
from PyQt6.QtCore import Qt, QThread, QTimer, QSize, QRunnable, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, QDockWidget \
    , QLabel, QWidget, QListWidget, QListWidgetItem, QMessageBox \
    , QComboBox, QTextEdit, QLineEdit, QPushButton, QFileDialog \
    , QDialog, QMenu, QWidgetAction, QCheckBox

from constants import *

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


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        self.fn(*self.args, **self.kwargs)


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
        if self.client.current_device:
            self.name_label = QLabel(f"You - {self.client.name}")
        else:
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
        self.all_items.pop(name)


class ChatWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # self.resize(800, 600)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.central_widget = QTextEdit(self)
        self.central_widget.setReadOnly(True)
        self.layout.addWidget(self.central_widget)

        self.clients_menu = QMenu("Clients", self)
        self.clients_menu.aboutToShow.connect(self.resize_clients_menu)
        self.clients_checkboxes = {}
        self.clients_menu_actions = {}

        self.select_all_checkbox, _ = self.add_client("") # Select All Checkbox
        self.clients_menu.addSeparator()

        self.clients_button = QPushButton("Clients", self)
        self.clients_button.setMenu(self.clients_menu)
        self.layout.addWidget(self.clients_button)

        self.file_button = QPushButton("Send File", self)
        self.layout.addWidget(self.file_button)

        self.bottom_layout = QHBoxLayout()
        self.layout.addLayout(self.bottom_layout)

        self.line_edit = QLineEdit(self)
        self.bottom_layout.addWidget(self.line_edit)

        self.send_button = QPushButton("Send", self)
        self.bottom_layout.addWidget(self.send_button)
    
    def add_client(self, name: str):
        checkbox = QCheckBox(name, self)
        checkbox.setChecked(True)
        action_widget = QWidgetAction(self)
        action_widget.setDefaultWidget(checkbox)
        self.clients_menu.addAction(action_widget)

        if name == "": # Select All Checkbox
            checkbox.setText("Select All")
            checkbox.stateChanged.connect(
                lambda state: self.on_checkbox_click(state, is_select_all=True)
            )
            return checkbox, action_widget
        
        checkbox.stateChanged.connect(
            lambda state: self.on_checkbox_click(state)
        )
        self.clients_checkboxes[name] = checkbox
        self.clients_menu_actions[name] = action_widget
    
    def remove_client(self, name: str):
        self.clients_menu.removeAction(self.clients_menu_actions[name])
        self.clients_menu_actions.pop(name)
        self.clients_checkboxes.pop(name)

    def resize_clients_menu(self):
        self.clients_menu.setMinimumWidth(self.clients_button.width())
    
    def on_checkbox_click(self, is_checked: bool, is_select_all: bool = False):
        if is_select_all:
            for client_checkbox in self.clients_checkboxes.values():
                client_checkbox.blockSignals(True)
                client_checkbox.setChecked(is_checked)
                client_checkbox.blockSignals(False)
        else:
            if not is_checked:
                self.select_all_checkbox.blockSignals(True)
                self.select_all_checkbox.setChecked(False)
                self.select_all_checkbox.blockSignals(False)
    
    def selected_clients(self):
        selected = []
        for name, checkbox in self.clients_checkboxes.items():
            if checkbox.isChecked():
                selected.append(name)
        return tuple(selected)

    def get_file(self):
        file_path = QFileDialog.getOpenFileName(None, "Select File", options= QFileDialog.Option.DontUseNativeDialog)[0]
        return file_path

    def get_text(self):
        text = self.line_edit.text()
        self.line_edit.clear()
        return text
    
    def add_msg(self, from_name: str, to_name: str, msg: str):
        self.central_widget.append(f"[{from_name} 🠖 {to_name}] {msg}")


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
        if self.get_name() == "":
            QMessageBox.critical(self, "Error", "Username cannot be empty")
            return
        if " " in self.get_name():
            QMessageBox.critical(self, "Error", "Username cannot contain spaces")
            return
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
        self.server_conn.add_msg_signal.connect(self.add_msg)

        self.login_dialog = LoginDialog(self)
        if not self.login_dialog.exec():
            exit()
        
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
        self.chat_widget.send_button.clicked.connect(lambda: self.send_msg(TEXT))
        self.chat_widget.line_edit.returnPressed.connect(lambda: self.send_msg(TEXT))
        self.chat_widget.file_button.clicked.connect(lambda: self.send_msg(FILE))

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
        if not client.current_device:
            self.chat_widget.add_client(client.name)
    
    def remove_client(self, name: str):
        self.video_list_widget.remove_client(name)
        if ENABLE_AUDIO:
            self.audio_threads[name].terminate()
            self.audio_threads.pop(name)
        self.chat_widget.remove_client(name)

    def send_msg(self, data_type: str = TEXT):
        selected = self.chat_widget.selected_clients()
        if len(selected) == 0:
            QMessageBox.critical(self, "Error", "Select at least one client")
            return
        
        if data_type == TEXT:
            msg_text = self.chat_widget.get_text()
        elif data_type == FILE:
            filepath = self.chat_widget.get_file()
            if not filepath:
                return
            msg_text = os.path.basename(filepath)
        else:
            print(f"{data_type} data_type not supported")
            return
        
        if msg_text == "":
            QMessageBox.critical(self, "Error", f"{data_type} cannot be empty")
            return
        
        msg = Message(self.client.name, POST, data_type, data=msg_text, to_names=selected)
        self.server_conn.send_msg(self.server_conn.main_socket, msg)
        
        if data_type == FILE:
            send_file_thread = Worker(self.server_conn.send_file, filepath)
            self.server_conn.threadpool.start(send_file_thread)
            msg_text = f"Sending {msg_text}..."

        self.chat_widget.add_msg("You", ", ".join(selected), msg_text)
    
    def add_msg(self, from_name: str, msg: str):
        self.chat_widget.add_msg(from_name, "You", msg)
    
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
