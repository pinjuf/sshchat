#!/usr/bin/env python3
import logging
import socket
import sys
import threading
import random
from datetime import datetime

import paramiko

COLORS = [
    "\u001b[31m",
    "\u001b[32m",
    "\u001b[33m",
    "\u001b[34m",
    "\u001b[35m",
    "\u001b[36m",
    "\u001b[37m"]

COLOR_RESET = "\u001b[0m"

# CONFIG

RSA_PATH = "rsa.private"
PORT = 2222
SERVER_NAME = "PROUTROOM"

USERCFG = {}

logging.basicConfig()
logger = logging.getLogger()

host_key = paramiko.RSAKey.from_private_key_file(filename=RSA_PATH)

class ChatRoomServ(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        if not username in USERCFG.keys():
            print(f"New user: {username}|{password}")
            USERCFG[username] = [password, random.choice(COLORS)]
            return paramiko.AUTH_SUCCESSFUL

        if USERCFG[username][0] == password:
            return paramiko.AUTH_SUCCESSFUL

        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True

def send_global(msg="", context="MESSAGE", usercolor="???", target=False):
    if usercolor == "":
        usercolor = username
    for chan in chans:
        if target and chan._username not in target:
            continue
        chan.send("\033[u")
        chan.send(datetime.now().strftime("(%H:%M) "))
        if target:
            chan.send(f"*private (involves {', '.join(target)})* ")
        if context=="MESSAGE":
            chan.send(f"[{usercolor}] {msg}\r\n")
        if context=="JOIN":
            chan.send(f"{{LOG}} {usercolor} has joined!\r\n")
        if context=="EXIT":
            chan.send(f"{{LOG}} {usercolor} has exited!\r\n")
        chan.send("\033[s\033[0;f")

def handle_user_input(chan):
    while True:
        msg = ""
        while not msg.endswith("\r"):
            transport = chan.recv(1024)
            chan.send("\033[0;0f\r\033[K")
            if transport == b"\x7f":
                if len(msg):
                    msg = msg[:-1]
            elif transport == b"\x04":
                msg = "/exit"
                break
            else:
                msg += transport.decode("utf-8")
            chan.send(msg)
        chan.send("\033[0;0f\r\033[K")
        msg = msg.strip()

        if msg.startswith("/help"):
            send_global(msg="\r\n/help to call this help\r\n/exit to exit\r\n/msg [username] [msg]", target=chan._username, usercolor="*HELP*")
        elif msg.startswith("/exit"):
            send_global(context="EXIT", usercolor=chan._usernamecolor)
            chans.remove(chan)
            chan.send("\033[?25h\033[2J\033[0;0f")
            chan.close()
            print(f"{chan._username} has left")
            break
        elif msg.startswith("/msg"):
            if len(msg.split(" "))<3:
                continue
            target = msg.split(" ")[1]
            tmsg   = " ".join(msg.split(" ")[2:])
            send_global(usercolor=chan._usernamecolor, target=[target, chan._username], msg=tmsg)
        elif msg:
            send_global(msg=msg, usercolor=chan._usernamecolor)

def init_user(ca_pair):
    client, addr = ca_pair
    print(f"Connection from {addr[0]}!")

    transport = paramiko.Transport(client)
    transport.add_server_key(host_key)
    server = ChatRoomServ()
    try:
        transport.start_server(server=server)
    except Exception as ex:
        print(f"SSH negotiation failed for {addr[0]} failed. ({ex})")
        return
    chan = transport.accept(20)
    if not chan:
        print(f"No channel for {addr[0]}.")
        return

    chan._username = transport.get_username()
    print(f"User login: {chan._username}")
    chan._usernamecolor = USERCFG[chan._username][1]+chan._username+COLOR_RESET
    chans.append(chan)
    chan.send(f"\033[?25l\033[2J\033[2;0fWelcome to {SERVER_NAME}!\r\n\033[s")
    send_global(context="JOIN", usercolor=chan._usernamecolor)
    threading.Thread(target=handle_user_input, args=(chan,)).start()
    

def run_chatroom():
    global chans
    chans = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', PORT))

    while True:
        sock.listen(128)
        ca = sock.accept()
        threading.Thread(target=init_user, args=(ca,)).start()

print(f"Starting chatroom {SERVER_NAME}!")
run_chatroom()
