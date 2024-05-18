import socket
import threading
from constants import (
    SHIP_PLACEMENT_START_COMMAND, DISCONNECT_COMMAND, CLIENT_SHIP_PLACEMENT_COMMAND, CLIENT_SHOT_COMMAND, TURN_COMMAND, SHIP_PLACEMENT_END_COMMAND,
    SEE_BOARD_COMMAND, QUIT_COMMAND
)
from utils import parse_socket_message, send_message, receive_message
import sys

# Constants
PORT = 12345
SERVER_IP = "localhost"

# Flag to indicate if the client should keep running
running = True

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
                
            flag, command, server_msg = parse_socket_message(rcv_msg)
            if server_msg:
                print(f"Server: {server_msg}")
            if command == DISCONNECT_COMMAND:
                client_socket.close()
                running = False
                print("Disconnected from server.")
                sys.exit(0)
            elif command == SHIP_PLACEMENT_START_COMMAND:
                threading.Thread(target=start_ships_placement, args=(client_socket,)).start()
            elif command == TURN_COMMAND:
                threading.Thread(target=handle_shooting, args=(client_socket,)).start()
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
        placement = input("Enter ship placement (format: <ship_name>:<x><y>:<orientation>): ")
        try:
            send_message(client_socket, placement, command=CLIENT_SHIP_PLACEMENT_COMMAND)
            msg_type, command, message = wait_for_socket_response(client_socket)
            print(message)
            
            if command == SHIP_PLACEMENT_END_COMMAND:
                break
        except ValueError as e:
            print(f"Invalid placement (format: <ship_name>:<x><y>:<orientation>). Please try again.")
        except ConnectionAbortedError:
            print("Server aborted connection.")
            break

def handle_shooting(client_socket):
    while True:
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
        listen_to_server(client_socket)

if __name__ == "__main__":
    main()
