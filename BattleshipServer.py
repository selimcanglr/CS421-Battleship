import socket
import threading
import select
from constants import (
    SHIP_PLACEMENT_START_COMMAND, ERROR_FLAG, INFO_FLAG, INVALID_REQUEST_FLAG,
    CLIENT_SHIP_PLACEMENT_COMMAND, CLIENT_SHOT_COMMAND, SHIP_PLACEMENT_END_COMMAND,
    DISCONNECT_COMMAND, SEE_BOARD_COMMAND, TURN_COMMAND
)
from utils import parse_socket_message, send_message, receive_message

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
    server.listen()
    server.setblocking(0)
    return server

def disconnection_cleanup(client_socket, client_id):
    global client_id_counter

    if client_id not in clients or clients[client_id]["socket"] != client_socket:
        return
    try:
        send_message(client_socket, "You have been disconnected from the server.", type=ERROR_FLAG, command=DISCONNECT_COMMAND)
    except OSError:
        pass
    
    client_socket.close()
    client_id_counter -= 1
    del clients[client_id]
    print(f"Client {client_id} disconnected and cleaned up.")

def is_valid_placement(board, ship_size, x, y, orientation):
    if orientation == 'H':
        if y + ship_size > BOARD_SIZE:
            return False, "Out of bounds horizontally"
        for i in range(ship_size):
            if board[x][y + i] != '~':
                return False, "Another ship is already placed at the location"
    elif orientation == 'V':
        if x + ship_size > BOARD_SIZE:
            return False, "Out of bounds vertically"
        for i in range(ship_size):
            if board[x + i][y] != '~':
                return False, "Another ship is already placed at the location"
    return True, ""

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

def remaining_ships(client_id):
    remaining = {name: {"count": SHIPS[name]['count'] - GAME_STATE[client_id]['ships'].get(name, 0), "size": SHIPS[name]["size"]} for name in SHIPS}
    return format_ships(remaining)

def all_ships_sunk(board):
    for row in board:
        if 'S' in row:
            return False
    return True

def format_hits_misses(hits, misses):
    # Initialize the board with empty spaces
    board = [['~' for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    
    # Mark the hits with 'X'
    for x, y in hits:
        board[x][y] = 'X'
    
    # Mark the misses with 'O'
    for x, y in misses:
        board[x][y] = 'O'
    
    # Convert the board to a string format
    board_str = "\n".join([" ".join(row) for row in board])
    return board_str

def send_board_and_turn_info():
    for cid in clients:
        opponent_id = next(id for id in GAME_STATE if id != cid)
        board_str = format_board(GAME_STATE[cid]['board'])
        hits_misses_str = format_hits_misses(GAME_STATE[opponent_id]['hits'], GAME_STATE[opponent_id]['misses'])
        send_message(clients[cid]["socket"], f"Your board:\n{board_str}\nHits and misses:\n{hits_misses_str}", type=INFO_FLAG)
    
    current_turn = GAME_STATE["current_turn"]
    send_message(clients[current_turn]["socket"], "Your turn!", type=INFO_FLAG, command=TURN_COMMAND)
    other_turn = next(cid for cid in GAME_STATE if cid != current_turn)
    send_message(clients[other_turn]["socket"], "Wait for the other player.", type=INFO_FLAG)

def handle_ship_placement(client_socket, client_id, msg):
    try:
        ship_name, position, orientation = msg.split(":")
        x, y = int(position[0]), int(position[1])
        print(f"Client {client_id} is placing {ship_name} at {position} facing {orientation}.")
        if ship_name not in SHIPS:
            send_message(client_socket, f"{ship_name} does not exist as a ship. Ships are: {format_ships(SHIPS)}", type=INVALID_REQUEST_FLAG)
            return
        if GAME_STATE.get(client_id, {}).get("ships_placed", False):
            send_message(client_socket, "Ships have already been placed.", type=INVALID_REQUEST_FLAG)
            return
        if GAME_STATE[client_id]["ships"].get(ship_name, 0) >= SHIPS[ship_name]["count"]:
            send_message(client_socket, f"All {ship_name}(s) have already been placed.", type=INVALID_REQUEST_FLAG)
            return
        valid, reason = is_valid_placement(GAME_STATE[client_id]["board"], SHIPS[ship_name]["size"], x, y, orientation)
        if not valid:
            send_message(client_socket, f"{ship_name} cannot be placed at {position} facing {orientation}. Reason: {reason}", type=INVALID_REQUEST_FLAG)
            return

        place_ship_on_board(GAME_STATE[client_id]["board"], SHIPS[ship_name]["size"], x, y, orientation)
        GAME_STATE[client_id]["ships"][ship_name] = GAME_STATE[client_id]["ships"].get(ship_name, 0) + 1
        print(f"Placing {ship_name} at {position} facing {orientation}.")
        if len(GAME_STATE[client_id]["ships"]) == len(SHIPS):
            GAME_STATE[client_id]["ships_placed"] = True
            send_message(client_socket, f"Board placement complete, wait further instructions. Your board:\n{format_board(GAME_STATE[client_id]['board'])}.", type=INFO_FLAG, command=SHIP_PLACEMENT_END_COMMAND)
            if all(GAME_STATE[cid]["ships_placed"] for cid in GAME_STATE):
                for cid in GAME_STATE:
                    send_message(clients[cid]["socket"], "All players have placed their ships. The game is starting!", type=INFO_FLAG)
                GAME_STATE["current_turn"] = next(iter(GAME_STATE))  # Initialize the first turn
                send_board_and_turn_info()
        else:
            send_message(client_socket, f"Placed {ship_name} at {position} facing {orientation}. New board:\n{format_board(GAME_STATE[client_id]['board'])}\nRemaining ships:\n{remaining_ships(client_id)}")
            
    except (ValueError, IndexError):
        send_message(client_socket, "Command is incorrect. Correct format is: <ship_name>:<x><y>:<orientation>", type=INVALID_REQUEST_FLAG)

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
            send_message(client_socket, "You sunk all ships. You WIN!", type=INFO_FLAG)
            send_message(clients[target_client_id]["socket"], "All ships sunk. You LOSE!", type=INFO_FLAG)
            disconnection_cleanup(clients[target_client_id]["socket"], target_client_id)
    elif target_board[tx][ty] == 'X':
        send_message(client_socket, f"Already hit at {msg}.", type=INFO_FLAG)
    else:
        target_board[tx][ty] = 'O'  # Miss
        GAME_STATE[target_client_id]["misses"].append((tx, ty))
        send_message(client_socket, f"Miss at {msg}.", type=INFO_FLAG)

    # Update the turn
    GAME_STATE["current_turn"] = target_client_id if GAME_STATE["current_turn"] == client_id else client_id

    # Notify both clients of their board state and the turn information
    send_board_and_turn_info()

def handle_client_thread(client_socket, client_addr, client_id):
    global client_id_counter

    def check_ship_placement():
        for client_id, client_info in list(clients.items()):
            if client_id in GAME_STATE and not GAME_STATE[client_id].get("ships_placed", False):
                send_message(client_info["socket"], "Timeout! You failed to place your ships in time.", type=ERROR_FLAG, command=DISCONNECT_COMMAND)
                disconnection_cleanup(client_info["socket"], client_id)

    try:
        send_message(client_socket, f"You can type 'SEE_BOARD' to see the board and your ships.")

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
        timer = threading.Timer(SHIP_PLACEMENT_TIMEOUT, check_ship_placement)
        timer.start()

        while True:
            readable, _, _ = select.select([client_socket], [], [], 1.0)
            for s in readable:
                message = receive_message(client_socket)
                if not message:
                    print(f"Client {client_id} disconnected.")
                    return
                msg_type, msg_cmd, msg = parse_socket_message(message)
                try:
                    if msg_cmd == CLIENT_SHIP_PLACEMENT_COMMAND:
                        handle_ship_placement(client_socket, client_id, msg)
                    elif msg_cmd == CLIENT_SHOT_COMMAND:
                        handle_shot(client_socket, client_id, msg)
                    elif msg_cmd == DISCONNECT_COMMAND:
                        print(f"Client {client_id} requested to disconnect.")
                        disconnection_cleanup(client_socket, client_id)
                        return
                    elif msg_cmd == SEE_BOARD_COMMAND:
                        send_message(client_socket, f"Your current board:\n{format_board(GAME_STATE[client_id]['board'])}", type=INFO_FLAG)
                    else:
                        send_message(client_socket, "Command format is incorrect. Correct format is: <ship_name>:<x><y>:<orientation> or <x><y>", type=INVALID_REQUEST_FLAG)
                except (ValueError, IndexError):
                    send_message(client_socket, "Command is incorrect. Correct format is: <ship_name>:<x><y>:<orientation> or <x><y>", type=INVALID_REQUEST_FLAG)
                    return
    except OSError:
        print(f"Client {client_id} disconnected.")
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
            # Check for disconnected clients
            for client_id, client_info in list(clients.items()):
                client_socket = client_info["socket"]
                readable, _, _ = select.select([client_socket], [], [], 0.1)
                if client_socket in readable:
                    message = receive_message(client_socket)
                    if message is None:
                        print(f"Client {client_id} has disconnected.")
                        disconnection_cleanup(client_socket, client_id)

            # Accept new clients
            readable, _, _ = select.select([server], [], [], 1.0)
            for s in readable:
                client_socket, client_addr = s.accept()
                client_id_counter += 1
                client_id = client_id_counter
                clients[client_id] = {
                    "socket": client_socket,
                    "address": client_addr,
                    "id": client_id
                }
                print(f"Connection from {client_addr} has been established")
                send_message(client_socket, f"Welcome to Battleship! You are client {client_id}.")
                if len(clients) == MAX_CLIENTS:
                    for client in clients.values():
                        start_client_thread(client["socket"], client["address"], client["id"])
    except Exception as e:
        print(f"Error accepting client: {e}")
    finally:
        server.close()

    print("All clients have connected.")

def main():
    server = init_server()
    print(f"Server is listening on {ADDR}")

    accept_clients(server)

main()
