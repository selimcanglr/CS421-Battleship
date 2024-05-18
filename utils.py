import socket, time

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
        # Receive the header indicating the size of the message
        msg = client_socket.recv(1024)
        return msg.decode()
    except socket.error:
        return None

def send_message(client_socket, message, type="INFO", command="DEFAULT"):
    total_msg = f"{type}:{command}:{message}"
    client_socket.send(total_msg.encode())
    time.sleep(0.1)