import socket
import threading
import time
from constants import (
    SHIP_PLACEMENT_START_COMMAND, ERROR_FLAG, INFO_FLAG, INVALID_REQUEST_FLAG,
    CLIENT_SHIP_PLACEMENT_COMMAND, CLIENT_SHOT_COMMAND
)
from utils import parse_socket_message

# Server connection constants
PORT = 12345
SERVER = "localhost"
ADDR = (SERVER, PORT)
SHIP_PLACEMENT_TIMEOUT = 60
MAX_CLIENTS = 2

# Clients state
client_id_counter = 0
clients = {}

# Game constants
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
BOARD_SIZE = 5

# Game state
GAME_STATE = {}

def init_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(ADDR)
    server.setblocking(1)
    return server

def disconnection_cleanup(client_socket, client_id):
    if client_id not in clients:
        return

    global client_id_counter
    client_socket.close()
    client_id_counter -= 1
    del clients[client_id]

def is_valid_placement(board, ship_size, x, y, orientation):
    if orientation == 'H':
        if y + ship_size > BOARD_SIZE:
            return False
        for i in range(ship_size):
            if board[x][y + i] != '~':
                return False
    elif orientation == 'V':
        if x + ship_size > BOARD_SIZE:
            return False
        for i in range(ship_size):
            if board[x + i][y] != '~':
                return False
    return True

def place_ship_on_board(board, ship_size, x, y, orientation):
    if orientation == 'H':
        for i in range(ship_size):
            board[x][y + i] = 'S'
    elif orientation == 'V':
        for i in range(ship_size):
            board[x + i][y] = 'S'

def format_board(board):
    return "\n".join([" ".join(row) for row in board])

def format_ships(ships):
    return "\n".join([f"{name}: {info['count']} ship(s) of size {info['size']}" for name, info in ships.items()])

def all_ships_sunk(board):
    for row in board:
        if 'S' in row:
            return False
    return True

def send_message(client_socket, message, type="INFO", command="DEFAULT"):
    time.sleep(0.3)
    full_message = f"{type}:{command}:{message}".encode()
    client_socket.sendall(full_message)

def receive_message(client_socket):
    message = client_socket.recv(1024)
    return message

def check_ship_placement(timer, client_socket, client_id):
    if client_id in GAME_STATE and GAME_STATE[client_id].get("ships_placed", False):
        timer.cancel()
    elif client_id in GAME_STATE:
        send_message(client_socket, "Timeout! You failed to place your ships in time.", type=ERROR_FLAG)
        disconnection_cleanup(client_socket, client_id)

def handle_ship_placement(client_socket, client_id, msg):
    ship_name, position, orientation = msg.split(":")
    x, y = int(position[0]), int(position[1])
    if ship_name not in SHIPS:
        send_message(client_socket, f"{ship_name} does not exist as a ship. Ships are: {format_ships(SHIPS)}", type=INVALID_REQUEST_FLAG)
        return
    if GAME_STATE.get(client_id, {}).get("ships_placed", False):
        send_message(client_socket, "Ships have already been placed.", type=INVALID_REQUEST_FLAG)
        return
    if not is_valid_placement(GAME_STATE[client_id]["board"], SHIPS[ship_name]["size"], x, y, orientation):
        send_message(client_socket, f"{ship_name} cannot be placed at {position} facing {orientation}.", type=INVALID_REQUEST_FLAG)
        return
    place_ship_on_board(GAME_STATE[client_id]["board"], SHIPS[ship_name]["size"], x, y, orientation)
    GAME_STATE[client_id]["ships"][ship_name] = {
        "position": position,
        "orientation": orientation
    }
    
    if len(GAME_STATE[client_id]["ships"]) == len(SHIPS):
        GAME_STATE[client_id]["ships_placed"] = True
        send_message(client_socket, "All ships placed. Game is ready to start.", type=INFO_FLAG)
        if all(GAME_STATE[cid]["ships_placed"] for cid in GAME_STATE):
            for cid in GAME_STATE:
                send_message(clients[cid]["socket"], "All players have placed their ships. The game is starting!", type=INFO_FLAG)
            # Notify the first client to start
            send_message(clients[1]["socket"], "Your turn to shoot.", type=INFO_FLAG, command="YOUR_TURN")
    else:
        send_message(client_socket, f"Placed {ship_name} at {position} facing {orientation}. New board:\n{format_board(GAME_STATE[client_id]['board'])}")

def handle_shot(client_socket, client_id, msg):
    tx, ty = int(msg[0]), int(msg[1])
    target_client_id = next(cid for cid in GAME_STATE if cid != client_id)
    target_board = GAME_STATE[target_client_id]["board"]
    if target_board[tx][ty] == 'S':
        target_board[tx][ty] = 'X'  # Hit
        GAME_STATE[target_client_id]["hits"].append((tx, ty))
        send_message(client_socket, f"Hit at {msg}!", type=INFO_FLAG)
        send_message(clients[target_client_id]["socket"], f"Your ship was hit at {msg}!", type=INFO_FLAG)
        if all_ships_sunk(target_board):
            send_message(client_socket, "You sunk all ships. You win!", type=INFO_FLAG)
            send_message(clients[target_client_id]["socket"], "All ships sunk. You lose!", type=INFO_FLAG)
            disconnection_cleanup(clients[target_client_id]["socket"], target_client_id)
    else:
        target_board[tx][ty] = 'O'  # Miss
        GAME_STATE[target_client_id]["misses"].append((tx, ty))
        send_message(client_socket, f"Miss at {msg}.", type=INFO_FLAG)
    
    # Notify the next player to take their turn
    next_player_id = next(cid for cid in GAME_STATE if cid != client_id)
    send_message(clients[next_player_id]["socket"], "Your turn to shoot.", type=INFO_FLAG, command="YOUR_TURN")

def handle_client_thread(client_socket, client_addr, client_id):
    global client_id_counter

    send_message(client_socket, f"Welcome to Battleship! You are client {client_id}.")

    # Wait until both clients are connected
    while len(clients) < MAX_CLIENTS:
        time.sleep(1)

    # Create the board
    board = [['~' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    formatted_board = format_board(board)
    formatted_ships = format_ships(SHIPS)

    # Send client ID, board, and ships information
    send_message(client_socket, f"Your ID: {client_id}\nBoard:\n{formatted_board}\nYour Ships:\n{formatted_ships}\nShips can be placed horizontally or vertically.")
    GAME_STATE[client_id] = {
        "board": board,
        "ships": {},
        "ships_placed": False,
        "hits": [],
        "misses": [],
    }

    send_message(client_socket, "You have 60 seconds to place your ships.", command=SHIP_PLACEMENT_START_COMMAND)
    timer = threading.Timer(SHIP_PLACEMENT_TIMEOUT, check_ship_placement, [timer, client_socket, client_id])
    timer.start()

    while True:
        message = receive_message(client_socket)
        if not message:
            break
        msg_type, msg_cmd, msg = parse_socket_message(message)
        try:
            if msg_cmd == CLIENT_SHIP_PLACEMENT_COMMAND:
                handle_ship_placement(client_socket, client_id, msg)
            elif msg_cmd == CLIENT_SHOT_COMMAND:
                handle_shot(client_socket, client_id, msg)
            else:
                send_message(client_socket, "Command format is incorrect. Correct format is: <ship_name>:<x><y>:<orientation> or <x><y>", type=INVALID_REQUEST_FLAG)
        except (ValueError, IndexError):
            send_message(client_socket, "Command is incorrect. Correct format is: <ship_name>:<x><y>:<orientation> or <x><y>", type=INVALID_REQUEST_FLAG)
            break
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
