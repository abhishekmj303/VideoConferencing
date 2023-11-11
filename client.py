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
    def __init__(self, name: str, current_device = False):
        self.name = name
        self.current_device = current_device

        self.video_frame = None
        self.audio_data = None

        if self.current_device:
            self.camera = Camera()
            self.microphone = Microphone()
        else:
            self.camera = None
            self.microphone = None

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
        self.init_conn() # Connect to all servers and send name
        self.start_conn_threads() # Start receiving threads for all servers
        self.start_broadcast_threads() # Start sending threads for audio and video

        self.add_client_signal.emit(client)

        while self.connected:
            pass
        self.disconnect_server()

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
        self.main_conn_thread = Worker(self.handle_conn, self.main_socket, TEXT)
        self.threadpool.start(self.main_conn_thread)

        self.video_conn_thread = Worker(self.handle_conn, self.video_socket, VIDEO)
        self.threadpool.start(self.video_conn_thread)

        self.audio_conn_thread = Worker(self.handle_conn, self.audio_socket, AUDIO)
        self.threadpool.start(self.audio_conn_thread)

    def start_broadcast_threads(self):
        self.video_broadcast_thread = Worker(self.media_broadcast_loop, self.video_socket, VIDEO)
        self.threadpool.start(self.video_broadcast_thread)

        self.audio_broadcast_thread = Worker(self.media_broadcast_loop, self.audio_socket, AUDIO)
        self.threadpool.start(self.audio_broadcast_thread)
    
    def disconnect_server(self):
        self.main_socket.disconnect()
        self.video_socket.disconnect()
        self.audio_socket.disconnect()
    
    def send_msg(self, conn: socket.socket, msg: Message):
        conn.send_bytes(pickle.dumps(msg))
    
    def media_broadcast_loop(self, conn: socket.socket, media: str):
        while self.connected:
            if media == VIDEO:
                data = client.get_video()
            elif media == AUDIO:
                data = client.get_audio()
            else:
                print("Invalid media type")
                break
            msg = Message(self.name, POST, media, data)
            self.send_msg(conn, msg)

    def handle_conn(self, conn: socket.socket, media: str):
        while self.connected:
            msg_bytes = conn.recv_bytes()
            if not msg_bytes:
                self.connected = False
                break
            try:
                msg = pickle.loads(msg_bytes)
            except pickle.UnpicklingError:
                print(f"[{self.name}] [{media}] [ERROR] UnpicklingError")
                continue

            if msg.request == DISCONNECT:
                self.connected = False
                break
            try:
                self.handle_msg(msg)
            except Exception as e:
                print(f"[{self.name}] [{media}] [ERROR] {e}")
                continue

    def handle_msg(self, msg):
        if msg.request == POST:
            if msg.data_type == VIDEO:
                client.video_frame = msg.data
            elif msg.data_type == AUDIO:
                client.audio_data = msg.data
            else:
                print(f"[{self.name}] [ERROR] Invalid data type")
        elif msg.request == ADD:
            client_name = msg.from_name
            client_addr = msg.data
            all_clients[client_name] = Client(client_name, client_addr)
            self.add_client_signal.emit(all_clients[client_name])

client = Client("You", None)

all_clients = defaultdict(lambda: Client("", None))

if __name__ == "__main__":
    app = QApplication(sys.argv)

    server_conn = ServerConnection()
    window = MainWindow(client, server_conn)
    window.show()

    sys.exit(app.exec())