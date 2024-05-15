import socket

# Constants
PORT = 12345
SERVER_IP = "localhost"


def connect_to_server():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((SERVER_IP, PORT))
        print(f"Connected to server at {SERVER_IP}:{PORT}")
    except ConnectionRefusedError:
        print("Connection refused by server.")
        return None

    return client_socket


def listen_to_server(client_socket):
    while True:
        try:
            message = client_socket.recv(1024)
            if not message:
                break
            print(f"Received from server: {message.decode()}")
        except OSError:
            break


def main():
    client_socket = connect_to_server()
    listen_to_server(client_socket)


main()