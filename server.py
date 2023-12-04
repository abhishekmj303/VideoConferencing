import socket
import threading
import time
import os
import traceback
import pickle
from dataclasses import dataclass, field

from constants import *

IP = ''

clients = {} # list of clients connected to the server
video_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
audio_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
media_conns = {VIDEO: video_conn, AUDIO: audio_conn}

@dataclass
class Client:
    name: str
    main_conn: socket.socket
    connected: bool
    media_addrs: dict = field(default_factory=lambda: {VIDEO: None, AUDIO: None})

    def send_msg(self, from_name: str, request: str, data_type: str = None, data: any = None):
        msg = Message(from_name, request, data_type, data)
        try:
            if data_type in [VIDEO, AUDIO]:
                # print(f"[{self.name}] {self.media_addrs}")
                addr = self.media_addrs.get(data_type, None)
                if addr is None:
                    return
                media_conns[data_type].sendto(pickle.dumps(msg), addr)
            else:
                self.main_conn.send_bytes(pickle.dumps(msg))
        except (BrokenPipeError, ConnectionResetError, OSError):
            print(f"[{self.name}] [ERROR] BrokenPipeError or ConnectionResetError or OSError")
            self.connected = False


def broadcast_msg(from_name: str, request: str, data_type: str = None, data: any = None):
    all_clients = tuple(clients.values())
    for client in all_clients:
        if client.name == from_name:
            continue
        client.send_msg(from_name, request, data_type, data)


def multicast_msg(from_name: str, request: str, to_names: tuple[str], data_type: str = None, data: any = None):
    if not to_names:
        broadcast_msg(from_name, request, data_type, data)
        return
    for name in to_names:
        if name not in clients:
            continue
        clients[name].send_msg(from_name, request, data_type, data)


def media_server(media: str, port: int):
    conn = media_conns[media]
    conn.bind((IP, port))
    print(f"[LISTENING] {media} Server is listening on {IP}:{port}")

    while True:
        msg_bytes, addr = conn.recvfrom(MEDIA_SIZE[media])
        try:
            msg: Message = pickle.loads(msg_bytes)
        except pickle.UnpicklingError:
            print(f"[{addr}] [{media}] [ERROR] UnpicklingError")
            continue

        if msg.request == ADD:
            client = clients[msg.from_name]
            client.media_addrs[media] = addr
            print(f"[{addr}] [{media}] {msg.from_name} added")
        else:
            broadcast_msg(msg.from_name, msg.request, msg.data_type, msg.data)


def disconnect_client(client: Client):
    global clients

    print(f"[DISCONNECT] {client.name} disconnected from Main Server")
    client.media_addrs.update({VIDEO: None, AUDIO: None})
    client.connected = False

    broadcast_msg(client.name, RM)
    client.main_conn.disconnect()
    try:
        clients.pop(client.name)
    except KeyError:
        print(f"[ERROR] {client.name} not in clients")
        print(clients)
        pass


def handle_main_conn(name: str):
    client: Client = clients[name]
    conn = client.main_conn

    for client_name in clients:
        if client_name == name:
            continue
        client.send_msg(client_name, ADD)
    
    broadcast_msg(name, ADD)

    while client.connected:
        msg_bytes = conn.recv_bytes()
        if not msg_bytes:
            break
        try:
            msg = pickle.loads(msg_bytes)
        except pickle.UnpicklingError:
            print(f"[{name}] [ERROR] UnpicklingError")
            continue

        print(msg)
        if msg.request == DISCONNECT:
            break
        multicast_msg(name, msg.request, msg.to_names, msg.data_type, msg.data)
    
    disconnect_client(client)


def main_server():
    main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    main_socket.bind((IP, MAIN_PORT))
    main_socket.listen()
    print(f"[LISTENING] Main Server is listening on {IP}:{MAIN_PORT}")

    video_server_thread = threading.Thread(target=media_server, args=(VIDEO, VIDEO_PORT))
    video_server_thread.start()
    audio_server_thread = threading.Thread(target=media_server, args=(AUDIO, AUDIO_PORT))
    audio_server_thread.start()

    while True:
        conn, addr = main_socket.accept()
        name = conn.recv_bytes().decode()
        if name in clients:
            conn.send_bytes("Username already taken".encode())
            continue
        conn.send_bytes(OK.encode())
        clients[name] = Client(name, conn, True)
        print(f"[NEW CONNECTION] {name} connected to Main Server")

        main_conn_thread = threading.Thread(target=handle_main_conn, args=(name,))
        main_conn_thread.start()


if __name__ == "__main__":
    try:
        main_server()
    except KeyboardInterrupt:
        print(traceback.format_exc())
        print(f"[EXITING] Keyboard Interrupt")
        for client in clients.values():
            disconnect_client(client)
    except Exception as e:
        print(f"[ERROR] {e}")
        print(traceback.format_exc())
    finally:
        os._exit(0)