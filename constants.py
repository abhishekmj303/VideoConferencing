import socket
import struct
import pickle
from dataclasses import astuple, dataclass

PORT = 53535
MAIN_PORT = 53530
VIDEO_PORT = 53531
AUDIO_PORT = 53532
# ADDR = ('', PORT)
DISCONNECT = 'QUIT!'
OK = 'OK'
SIZE = 1024

SERVER = 'SERVER'

# requests
GET = 'GET'
POST = 'POST'
ADD = 'ADD'
RM = 'RM'

# data types
VIDEO = 'Video'
AUDIO = 'Audio'
TEXT = 'Text'
FILE = 'File'


def send_bytes(self, msg):
    # Prefix each message with a 4-byte length (network byte order)
    msg = struct.pack('>I', len(msg)) + msg
    self.sendall(msg)

def recv_bytes(self):
    # Read message length and unpack it into an integer
    raw_msglen = self.recvall(4)
    if not raw_msglen:
        return b''
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return self.recvall(msglen)

def recvall(self, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        try:
            packet = self.recv(n - len(data))
        except (BrokenPipeError, ConnectionResetError, OSError):
            print(f"[ERROR] Connection not present")
            return b''
        if not packet:
            return b''
        data.extend(packet)
    return data

def disconnect(self):
    msg = Message(SERVER, DISCONNECT)
    try:
        self.send_bytes(pickle.dumps(msg))
    except (BrokenPipeError, ConnectionResetError, OSError):
        print(f"[ERROR] Connection not present")
    self.close()

socket.socket.send_bytes = send_bytes
socket.socket.recv_bytes = recv_bytes
socket.socket.recvall = recvall
socket.socket.disconnect = disconnect

@dataclass
class Message:
    from_name: str
    request: str
    data_type: str = None
    data: any = None
    to_names: set[str] = None

    def __str__(self):
        if self.data_type in [VIDEO, AUDIO]:
            data = ""
        else:
            data = self.data
        return f"[{self.from_name}] {self.request}:{self.data_type} -> {self.to_names} {data}"

    def __iter__(self):
        return iter(astuple(self))
    
    def __getitem__(self, keys):
        return iter(getattr(self, k) for k in keys)
