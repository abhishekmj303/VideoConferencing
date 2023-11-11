import socket
import threading
import time
import os
import traceback
import pickle
from dataclasses import dataclass

from constants import *

IP = ''

registered = {} # all registered clients to the server
clients = {} # list of clients connected to the server

@dataclass
class Client:
    name: str
    main_conn: socket.socket
    addr: str
    connected: bool
    video_conn: socket.socket = None
    audio_conn: socket.socket = None

    def send_msg(self, from_name: str, request: str, data_type: str = None, data: any = None):
        msg = Message(from_name, request, data_type, data)
        if data_type == VIDEO:
            conn = self.video_conn
        elif data_type == AUDIO:
            conn = self.audio_conn
        else:
            conn = self.main_conn
        conn.send_bytes(pickle.dumps(msg))


def broadcast_msg(from_name: str, request: str, data_type: str = None, data: any = None):
    all_clients = tuple(clients.values())
    for client in all_clients:
        if client.name == from_name:
            continue
        client.send_msg(from_name, request, data_type, data)


def multicast_msg(from_name: str, request: str, to_names: set[str], data_type: str = None, data: any = None):
    if not to_names:
        broadcast_msg(from_name, request, data_type, data)
        return
    for name in to_names:
        if name not in clients:
            continue
        clients[name].send_msg(from_name, request, data_type, data)


def handle_media_conn(name: str, media: str):
    client = clients[name]
    if media == VIDEO:
        conn = client.video_conn
    elif media == AUDIO:
        conn = client.audio_conn
    
    while client.connected:
        msg_bytes = conn.recv_bytes()
        if not msg_bytes:
            break
        try:
            msg = pickle.loads(msg_bytes)
        except pickle.UnpicklingError:
            print(f"[{name}] [{media}] [ERROR] UnpicklingError")
            continue

        broadcast_msg(name, msg.request, msg.data_type, msg.data)
    
    conn.disconnect()
    if media == VIDEO:
        client.video_conn = None
    elif media == AUDIO:
        client.audio_conn = None


def media_server(media: str):
    if media == VIDEO:
        PORT = VIDEO_PORT
    elif media == AUDIO:
        PORT = AUDIO_PORT
        
    media_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    media_socket.bind((IP, PORT))
    media_socket.listen()
    print(f"[LISTENING] {media} Server is listening on {IP}:{PORT}")

    while True:
        conn, addr = media_socket.accept()
        name = conn.recv_bytes().decode()
        if name not in clients:
            conn.disconnect()
            continue
        if media == VIDEO:
            clients[name].video_conn = conn
        elif media == AUDIO:
            clients[name].audio_conn = conn
        print(f"[NEW CONNECTION] {name} connected to {media} Server")

        media_conn_thread = threading.Thread(target=handle_media_conn, args=(name, media))
        media_conn_thread.start()


def disconnect_client(client: Client):
    global clients

    broadcast_msg(client.name, RM)

    client.connected = False
    client.main_conn.disconnect()
    if client.video_conn:
        client.video_conn.disconnect()
    if client.audio_conn:
        client.audio_conn.disconnect()
    
    clients.pop(client.name)


def handle_main_conn(name: str):
    client = clients[name]
    conn = client.main_conn

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

    video_server_thread = threading.Thread(target=media_server, args=(VIDEO,))
    video_server_thread.start()
    audio_server_thread = threading.Thread(target=media_server, args=(AUDIO,))
    audio_server_thread.start()

    while True:
        conn, addr = main_socket.accept()
        name = conn.recv_bytes().decode()
        if name in clients:
            conn.disconnect()
            continue
        clients[name] = Client(name, conn, addr, True)
        broadcast_msg(name, ADD)
        print(f"[NEW CONNECTION] {name} connected to Main Server")

        main_conn_thread = threading.Thread(target=handle_main_conn, args=(name,))
        main_conn_thread.start()


if __name__ == "__main__":
    try:
        main_server()
    except KeyboardInterrupt:
        print(f"[EXITING] Keyboard Interrupt")
        print(traceback.format_exc())
        for client in clients.values():
            disconnect_client(client)
    except Exception as e:
        print(f"[ERROR] {e}")
        print(traceback.format_exc())
    finally:
        os._exit(0)