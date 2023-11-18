import os
import time
import sys
import socket
import pickle
from collections import defaultdict

from PyQt6.QtCore import QThreadPool, QRunnable, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMessageBox
from qt_gui import MainWindow, Camera, Microphone, Worker

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
        
        self.camera_enabled = True
        self.microphone_enabled = True

    def get_video(self):
        if not self.camera_enabled:
            return None

        if self.camera is not None:
            return self.camera.get_frame()

        return self.video_frame
    
    def get_audio(self):
        if not self.microphone_enabled:
            return None

        if self.microphone is not None:
            return self.microphone.get_data()

        return self.audio_data


class ServerConnection(QThread):
    add_client_signal = pyqtSignal(Client)
    remove_client_signal = pyqtSignal(str)
    add_msg_signal = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.threadpool = QThreadPool()

        self.main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.connected = False
        self.recieving_filename = None

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

        client.name = self.name
        name_bytes = self.name.encode()
        self.main_socket.send_bytes(name_bytes)
        conn_status = self.main_socket.recv_bytes().decode()
        if conn_status != OK:
            QMessageBox.critical(None, "Error", conn_status)
            self.main_socket.close()
            os._exit(1)

        self.connected = True
        self.video_socket.connect((IP, VIDEO_PORT))
        self.audio_socket.connect((IP, AUDIO_PORT))
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
        self.send_msg(self.main_socket, Message(self.name, DISCONNECT))
        self.main_socket.disconnect()
        self.video_socket.disconnect()
        self.audio_socket.disconnect()
    
    def send_msg(self, conn: socket.socket, msg: Message):
        # print("Sending..", msg)
        try:
            conn.send_bytes(pickle.dumps(msg))
        except (BrokenPipeError, ConnectionResetError, OSError):
            print(f"[ERROR] Connection not present")
            self.connected = False
    
    def send_file(self, filepath: str):
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            data = f.read(SIZE)
            while data:
                msg = Message(self.name, POST, FILE, data)
                self.send_msg(self.main_socket, msg)
                data = f.read(SIZE)
            msg = Message(self.name, POST, FILE, None)
            self.send_msg(self.main_socket, msg)
        self.add_msg_signal.emit(self.name, f"File {filename} sent.")
    
    def media_broadcast_loop(self, conn: socket.socket, media: str):
        while self.connected:
            if media == VIDEO:
                data = client.get_video()
            elif media == AUDIO:
                data = client.get_audio()
            else:
                print(f"[ERROR] Invalid media type")
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

    def handle_msg(self, msg: Message):
        global all_clients
        client_name = msg.from_name
        if msg.request == POST:
            if client_name not in all_clients:
                print(f"[{self.name}] [ERROR] Invalid client name")
                return
            if msg.data_type == VIDEO:
                all_clients[client_name].video_frame = msg.data
            elif msg.data_type == AUDIO:
                all_clients[client_name].audio_data = msg.data
            elif msg.data_type == TEXT:
                self.add_msg_signal.emit(client_name, msg.data)
            elif msg.data_type == FILE:
                if type(msg.data) == str:
                    self.recieving_filename = msg.data
                    with open(msg.data, 'wb') as f:
                        pass
                elif msg.data is None:
                    self.add_msg_signal.emit(client_name, f"File {self.recieving_filename} recieved.")
                    self.recieving_filename = None
                else:
                    with open(self.recieving_filename, 'ab') as f:
                        f.write(msg.data)
            else:
                print(f"[{self.name}] [ERROR] Invalid data type")
        elif msg.request == ADD:
            if client_name in all_clients:
                print(f"[{self.name}] [ERROR] Client already exists")
                return
            all_clients[client_name] = Client(client_name)
            self.add_client_signal.emit(all_clients[client_name])
        elif msg.request == RM:
            if client_name not in all_clients:
                print(f"[{self.name}] [ERROR] Invalid client name")
                return
            self.remove_client_signal.emit(client_name)
            all_clients.pop(client_name)

client = Client("You", current_device=True)

all_clients = defaultdict(lambda: Client(""))

if __name__ == "__main__":
    app = QApplication(sys.argv)

    server_conn = ServerConnection()
    window = MainWindow(client, server_conn)
    window.show()

    status_code = app.exec()
    server_conn.disconnect_server()
    os._exit(status_code)