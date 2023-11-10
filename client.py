import sys
import socket
import pickle
from collections import defaultdict

from PyQt6.QtCore import QThreadPool, QRunnable, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication
from qt_gui import MainWindow, Camera, Microphone

from constants import *

IP = socket.gethostbyname(socket.gethostname())
# ADDR = (IP, MAIN_PORT)


class Client:
    def __init__(self, name, addr):
        self.name = name
        self.addr = addr
        self.camera = None
        self.microphone = None

        self.video_frame = None
        self.audio_data = None

        if self.addr is None:
            self.camera = Camera()
            self.microphone = Microphone()

    def get_video(self):
        if self.camera is not None:
            return self.camera.get_frame()

        return self.video_frame
    
    def get_audio(self):
        if self.microphone is not None:
            return self.microphone.get_data()

        return self.audio_data


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


class ServerConnection(QThread):
    add_client_signal = pyqtSignal(Client)
    remove_client_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.threadpool = QThreadPool()

        self.main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.connected = False

    def run(self):
        self.init_conn()
        self.start_conn_threads()
        self.start_media_threads()

        self.add_client_signal.emit(client)

    def init_conn(self):
        self.main_socket.connect((IP, MAIN_PORT))
        self.video_socket.connect((IP, VIDEO_PORT))
        self.audio_socket.connect((IP, AUDIO_PORT))

        self.name = input("Client name: ")
        client.name = self.name
        self.connected = True

        name_bytes = self.name.encode()
        self.main_socket.send_bytes(name_bytes)
        self.video_socket.send_bytes(name_bytes)
        self.audio_socket.send_bytes(name_bytes)
    
    def start_conn_threads(self):
        pass

    def start_media_threads(self):
        pass
    
    def media_broadcast_loop(self, conn, media):
        pass

    def handle_conn(self, conn, media):
        pass

    def handle_msg(self, msg):
        pass

client = Client("You", None)

all_clients = defaultdict(lambda: Client("", None))

if __name__ == "__main__":
    app = QApplication(sys.argv)

    server_conn = ServerConnection()
    window = MainWindow(client, server_conn)
    window.show()

    sys.exit(app.exec())