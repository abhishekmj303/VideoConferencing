import sys
import socket

from PyQt6.QtWidgets import QApplication
from qt_gui import MainWindow, Camera, Microphone


class Client:
    def __init__(self, name, addr):
        self.name = name
        self.addr = addr
        self.camera = None
        self.microphone = None

        if self.addr is None:
            self.camera = Camera()
            self.microphone = Microphone()

    def get_video(self):
        if self.camera is not None:
            return self.camera.get_frame()
    
    def get_audio(self):
        if self.microphone is not None:
            return self.microphone.get_data()
        return None

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client = Client("Client", None)


def main():
    app = QApplication(sys.argv)

    window = MainWindow(client)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()