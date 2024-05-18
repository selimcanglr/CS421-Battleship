import socket
import threading
from constants import (
    SHIP_PLACEMENT_START_COMMAND, DISCONNECT_COMMAND, CLIENT_SHIP_PLACEMENT_COMMAND, CLIENT_SHOT_COMMAND, TURN_COMMAND, SHIP_PLACEMENT_END_COMMAND,
    SEE_BOARD_COMMAND, QUIT_COMMAND
)
from utils import parse_socket_message, send_message, receive_message
import sys
import queue

# Constants
PORT = 12345
SERVER_IP = "localhost"

# Flag to indicate if the client should keep running
running = True

# Queue for communicating between threads
message_queue = queue.Queue()

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
    global running
    while running:
        try:
            rcv_msg = receive_message(client_socket)
            if not rcv_msg:
                break
            if rcv_msg is None:
                print("Server disconnected.")
                running = False
                sys.exit(0)
                
            flag, command, server_msg = parse_socket_message(rcv_msg)
            message_queue.put((flag, command, server_msg))

            if server_msg:
                print(f"Server: {server_msg}")
            if command == DISCONNECT_COMMAND:
                client_socket.close()
                running = False
                print("Disconnected from server.")
                sys.exit(0)
            elif command == SHIP_PLACEMENT_START_COMMAND:
                start_ships_placement(client_socket)
            elif command == TURN_COMMAND:
                handle_shooting(client_socket)
        except OSError:
            break

def wait_for_socket_response(client_socket):
    try:
        rcv_msg = receive_message(client_socket)
        if not rcv_msg:
            return None, None, None
        flag, command, server_msg = parse_socket_message(rcv_msg)
        return flag, command, server_msg
    except OSError as e:
        print(f"Error: {e}")
        return None, None, None

def start_ships_placement(client_socket):
    while True:
        if not message_queue.empty():
            flag, command, server_msg = message_queue.get()
            if command == DISCONNECT_COMMAND:
                print("Server disconnected.")
                return
            if command == SHIP_PLACEMENT_END_COMMAND:
                break

        placement = input("Enter ship placement (format: <ship_name>:<x><y>:<orientation>, e.g. Mothership:01:H or Mothership:01:V): ")
        if placement == "QUIT":
            send_message(client_socket, "", command=QUIT_COMMAND)
            break
        elif placement == "SEE_BOARD":
            send_message(client_socket, "", command=SEE_BOARD_COMMAND)
            msg_type, command, message = wait_for_socket_response(client_socket)
            print(message)
            continue
        try:
            send_message(client_socket, placement, command=CLIENT_SHIP_PLACEMENT_COMMAND)
            msg_type, command, message = wait_for_socket_response(client_socket)
            print(message)
            if command == SHIP_PLACEMENT_END_COMMAND:
                break
        except ValueError as e:
            print(f"Invalid placement (format: <ship_name>:<x><y>:<orientation>, e.g. Mothership:01:H or Mothership:01:V). Please try again.")
        except ConnectionAbortedError:
            print("Server aborted connection.")
            break

def handle_shooting(client_socket):
    while True:
        if not message_queue.empty():
            flag, command, server_msg = message_queue.get()
            if command == DISCONNECT_COMMAND:
                print("Server disconnected.")
                return

        shot = input("Enter shot coordinates (format: <x><y>): ")
        try:
            send_message(client_socket, shot, command=CLIENT_SHOT_COMMAND)
            msg_type, command, message = wait_for_socket_response(client_socket)
            print(message)
            if command != "YOUR_TURN":
                break  # If it's not your turn anymore, break the loop
        except ConnectionAbortedError:
            print("Server aborted connection.")
            break

def main():
    client_socket = connect_to_server()
    if client_socket:
        listener_thread = threading.Thread(target=listen_to_server, args=(client_socket,))
        listener_thread.start()
        listener_thread.join()

if __name__ == "__main__":
    main()
