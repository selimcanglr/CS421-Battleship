import time 

def parse_socket_message(message):
    decoded_message = message.decode()
    parts = decoded_message.split(":", 2)
    if len(parts) < 3:
        raise ValueError("Message format incorrect")
    flag = parts[0]
    command = parts[1]
    server_msg = parts[2]
    return flag, command, server_msg


def send_message(message, client_socket, type="INFO", command="DEFAULT"):
    total_msg = f"{type}:{command}:{message}"
    client_socket.send(total_msg.encode())
    time.sleep(0.1)