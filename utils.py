import socket

def parse_socket_message(message):
    decoded_message = message
    parts = decoded_message.split(":", 2)
    if len(parts) < 3:
        raise ValueError("Message format incorrect")
    flag = parts[0]
    command = parts[1]
    server_msg = parts[2]
    return flag, command, server_msg


def receive_message(client_socket):
    try:
        header = client_socket.recv(4)
        if not header:
            return None
        msg_size = int.from_bytes(header, 'big')
        message = b""
        while len(message) < msg_size:
            chunk = client_socket.recv(msg_size - len(message))
            if not chunk:
                return None
            message += chunk
        return message.decode()
    except socket.error:
        return None

def send_message(client_socket, message, type="INFO", command="DEFAULT"):
    total_msg = f"{type}:{command}:{message}"
    msg_bytes = total_msg.encode()
    msg_size = len(msg_bytes)
    header = msg_size.to_bytes(4, 'big')
    client_socket.send(header + msg_bytes)