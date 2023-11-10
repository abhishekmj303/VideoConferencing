import sys
import socket
import pickle
from collections import defaultdict

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication
from qt_gui import MainWindow, Camera, Microphone

from constants import *

IP = socket.gethostbyname(socket.gethostname())
ADDR = (IP, MAIN_PORT)


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


class ServerConnection(QThread):
    add_client_signal = pyqtSignal(Client)
    remove_client_signal = pyqtSignal(str)

    def __init__(self, socket: socket.socket, parent=None):
        super().__init__(parent)
        self.socket = socket
    
    def run(self):
        self.socket.connect(ADDR)
        client.name = input("Client name: ")
        self.socket.send_msg(client.name.encode())
        self.handle_server()

    def handle_server(self):
        connected = True
        while connected:
            try:
                data = self.socket.recv_msg()
            except OSError:
                return
            try:
                msg: Message = pickle.loads(data)
            except pickle.UnpicklingError:
                continue
            except EOFError:
                msg = None
            if not msg or msg.request == DISCONNECT_MESSAGE:
                connected = False
                break

            try:
                self.handle_msg(msg)
            except Exception as e:
                print(f"[ERROR] {e}")

        # try:
        #     disconnect_server(client, "server")
        # except Exception:
        #     pass
        self.socket.close()
    
    def handle_msg(self, msg: Message):
        global client
        # print(msg)
        name, request, data_type, data = msg
        if request == GET:
            if data_type == VIDEO:
                video_frame = client.get_video()
                self.send_msg(POST, VIDEO, video_frame)
            elif data_type == AUDIO:
                audio_data = client.get_audio()
                self.send_msg(POST, AUDIO, audio_data)
            elif data_type == FILE:
                file_name = data
                #TODO: send file until EOF
                pass
        elif request == POST:
            if data_type == VIDEO:
                all_clients[name].video_frame = data
            elif data_type == AUDIO:
                all_clients[name].audio_data = data
            elif data_type == TEXT:
                window.add_msg(name, msg=data)
            elif data_type == FILE:
                file_name = data
                #TODO: receive file until EOF
                pass
        elif request == ADD:
            print(msg)
            if name == client.name:
                return
            new_client = Client(name, addr=data)
            all_clients[name] = new_client
            self.add_client_signal.emit(new_client)
        elif request == RM:
            print(msg)
            if name not in all_clients:
                return
            self.remove_client_signal.emit(name)
            del all_clients[name]
    
    def send_msg(self, request: str, data_type: str = None, data: any = None):
        msg_bytes = pickle.dumps(Message(client.name, request, data_type, data))
        # print(f"[SENDING] size={len(msg_bytes)}")
        self.socket.send_msg(msg_bytes)


client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client = Client("You", None)

all_clients = defaultdict(lambda: Client("", None))

if __name__ == "__main__":
    app = QApplication(sys.argv)

    server_conn = ServerConnection(client_socket)
    window = MainWindow(client, server_conn)
    window.show()

    sys.exit(app.exec())