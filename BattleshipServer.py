'''
    DESIGN:
    - Accept a connection from a client and initiate a thread to handle the client
    - Assign a unique ID to each client
    - Send the client its ID, the 5x5x board, and the list of ships (names, counts, and sizes) and inform the client
    that ships can be placed horizontally or vertically
    - Give 60 seconds for the client to place its ships, otherwise, disconnect the client
    - If all the ships are placed, inform the client that the game is ready to start
    - Notify the client if ship placement is invalid, do not reset the timer
    - If at the end of the 60 seconds, the client has not placed all the ships, disconnect the client
    - Store each client's board and ships, and turn information in a dictionary
    - Validate the client's shots and update the client's board
    - Notify if torpedo hits a target
    - Notify if the torpedo misses a target
    - Notify if a ship is sunk
    - Notify if all ships are sunk
    - Notify if their ship is sunk/hit
    - Check winning conditions at each turn and notify the client if they have won or lost
'''

import socket
import threading

# Constants
PORT = 12345
SERVER = "localhost"
ADDR = (SERVER, PORT)
TIMEOUT = 60
MAX_CLIENTS = 2
client_id_counter = 0
clients = {}

GAME_STATE = {}
SHIPS = {
    "Mothership": {
        "count": 1,
        "size": 4
    },
    "Destroyer": {
        "count": 1,
        "size": 3
    },
    "Submarine": {
        "count": 1,
        "size": 2
    },
}



def init_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(ADDR)
    server.setblocking(1)
    return server

def disconnection_cleanup(client_socket, client_id):
    global client_id_counter
    client_socket.close()
    client_id_counter -= 1
    del clients[client_id]


def handle_client_thread(client_socket, client_addr, client_id):
    global client_id_counter

    def send_message(message):
        client_socket.send(message.encode())

    def receive_message():
        return client_socket.recv(1024).decode()

    send_message(f"Welcome to Battleship! You are client {client_id}.")

    try:
        while True:
            message = client_socket.recv(1024)
            if not message:
                break
            print(f"Received from client {client_id}: {message.decode()}")
            client_socket.send(f"Ack: {message.decode()}".encode())
    except OSError:
        print(f"Client {client_id} has disconnected.")
    finally:
        disconnection_cleanup(client_socket, client_id)


def start_client_thread(client_socket, client_addr, client_id):
    client_thread = threading.Thread(target=handle_client_thread, args=(client_socket, client_addr, client_id))
    client_thread.start()


def accept_clients(server):
    global client_id_counter
    print("Waiting for clients to connect...")

    try:
        while len(clients) < MAX_CLIENTS:
            client_socket, client_addr = server.accept()
            client_id_counter += 1
            client_id = client_id_counter
            clients[client_id] = {
                "socket": client_socket,
                "address": client_addr,
                "id": client_id
            }
            print(f"Connection from {client_addr} has been established")
            start_client_thread(client_socket, client_addr, client_id)
    except Exception as e:
        print(f"Error accepting client: {e}")
    finally:
        server.close()

    print("All clients have connected.")


def main():
    server = init_server()
    server.listen()
    print(f"Server is listening on {ADDR}")

    accept_clients(server)


main()