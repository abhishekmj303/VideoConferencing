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
    conn: socket.socket
    addr: str
    connected: bool
    video_conn: socket.socket = None
    audio_conn: socket.socket = None

    def send_msg(self, from_name: str, request: str, data_type: str = None, data: any = None):
        msg = Message(from_name, request, data_type, data)
        # if data_type == VIDEO:
        #     conn = self.video_conn
        # elif data_type == AUDIO:
        #     conn = self.audio_conn
        # else:
        #     conn = self.main_conn
        self.conn.send_msg(pickle.dumps(msg))


def disconnect_client(client: Client):
    global clients
    print(f"[DISCONNECT CLIENT] {client.name} {client.addr} disconnected.")

    server_broadcast(request=RM, data=client.name)

    client.connected = False
    del clients[client.name]


def server_broadcast(request: str, data_type: str = None, data: any = None):
    clients_values = tuple(clients.values())
    for client in clients_values:
        client.send_msg(SERVER, request, data_type, data)


def client_broadcast(from_name: str, request: str, data_type: str = None, data: any = None):
    clients_values = tuple(clients.values())
    for client in clients_values:
        if client.name == from_name:
            continue
        client.send_msg(from_name, request, data_type, data)


def broadcast_loop(data_type: str):
    while True:
        server_broadcast(request=GET, data_type=data_type)


def handle_msg(client: Client, msg: Message):
    # print(msg)
    from_name, request, data_type, data = msg
    if request == GET:
        pass
    elif request == POST:
        client_broadcast(from_name, request, data_type, data)


def handle_client(client: Client):
    name, conn, addr = client.name, client.conn, client.addr
    print(f"[NEW CONNECTION] {name} {addr} connected.")

    for k in clients.keys():
        if k == name:
            continue
        client.send_msg(k, ADD, data=clients[k].addr)
        time.sleep(0.01)
    
    client_broadcast(name, ADD, data=addr)
    
    while client.connected:
        try:
            data = conn.recv_msg()
        except OSError:
            return
        try:
            msg: Message = pickle.loads(data)
        except pickle.UnpicklingError:
            continue
        except Exception as e:
            print(e)
            msg = None
        if not msg or msg.request == DISCONNECT_MESSAGE:
            client.connected = False
            break
        
        try:
            handle_msg(client, msg)
        except Exception as e:
            print(f"[ERROR] {e}")

    try:
        disconnect_client(client)
    except Exception as e:
        print(e)


# def handle_client_media(client: Client, data_type: str):
#     conn = client.video_conn if data_type == VIDEO else client.audio_conn
#     while client.connected:
#         media_bytes = b''
#         data = conn.recv_msg(SIZE)
#         while data:
#             media_bytes += data
#             data = conn.recv_msg(SIZE)
#         try:
#             msg: Message = pickle.loads(media_bytes)
#         except pickle.UnpicklingError:
#             print(f"[ERROR] [{client.name}] UnpicklingError")
#             continue
#         client_broadcast(client.name, POST, data_type, media_bytes)


# def video_server_loop():
#     server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     server.bind((IP, VIDEO_PORT))
#     server.listen()

#     print(f"[LISTENING] Video server is listening on {IP}:{VIDEO_PORT}")

#     while True:
#         conn, addr = server.accept()
#         name = conn.recv(SIZE).decode()
#         if name not in clients or clients[name].video_conn:
#             conn.send(f"Not able to connect video for client {name}".encode())
#             conn.close()
#             continue
        
#         conn.send(OK.encode())
#         clients[name].video_conn = conn

# def audio_server_loop():
#     server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     server.bind((IP, AUDIO_PORT))
#     server.listen()

#     print(f"[LISTENING] Audio server is listening on {IP}:{AUDIO_PORT}")

#     while True:
#         conn, addr = server.accept()
#         name = conn.recv(SIZE).decode()
#         if name not in clients or clients[name].audio_conn:
#             conn.send(f"Not able to connect video for client {name}".encode())
#             conn.close()
#             continue
        
#         conn.send(OK.encode())
#         clients[name].audio_conn = conn



def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((IP, MAIN_PORT))
    server.listen()

    print(f"[LISTENING] Server is listening on {IP}:{PORT}")

    video_thread = threading.Thread(target=broadcast_loop, args=(VIDEO,))
    video_thread.start()
    audio_thread = threading.Thread(target=broadcast_loop, args=(AUDIO,))
    audio_thread.start()

    while True:
        conn, addr = server.accept()
        name = conn.recv_msg().decode()
        client = Client(name, conn, f"{addr[0]}:{addr[1]}", True)
        if name in clients:
            client.send_msg(SERVER, DISCONNECT_MESSAGE)
            client.conn.close()
            continue
        clients[name] = client

        # client_broadcast(name, ADD, data=client.addr)

        thread = threading.Thread(target=handle_client, args=(client,))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

if __name__ == "__main__":
    try:
        main()
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