#!/usr/bin/env python3
import logging
import socket
import sys
import threading
import random
import hashlib
from getopt import getopt
import pickle
import os
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

USER_CFG_PATH = "usercfg.data"
RSA_PATH = "rsa.private"
PORT = 2222
SERVER_NAME = "PROUTROOM"

if os.path.exists(USER_CFG_PATH):
    with open(USER_CFG_PATH, "rb") as file:
        USER_CFG = pickle.load(file)
else:
    USER_CFG = {}

# logger setup, just in case
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
        # if user not registered, register with entered password (stored as sha256)
        if not username in USER_CFG.keys():
            print(f"New user: {username}|{password}")
            USER_CFG[username] = [hashlib.sha256(password.encode()).digest(), random.choice(COLORS)]

            # store data
            with open(USER_CFG_PATH, "wb") as file:
                 pickle.dump(USER_CFG, file)

            return paramiko.AUTH_SUCCESSFUL

        if USER_CFG[username][0] == hashlib.sha256(password.encode()).digest():
            return paramiko.AUTH_SUCCESSFUL

        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True

def build_status(userchan):
    output = f"[CHATROOM STATUS]\r\nServer name: {SERVER_NAME}\r\nCurrently {len(chans)} user(s) online.\r\nYour username: [{userchan._usernamecolor}]\r\n"
    return output

def send_global(msg="", context="MESSAGE", usercolor="???", target=False):
    for chan in chans.copy():
        try:
            # check if user is targeted
            if target and chan._username not in target:
                continue

            # reset cursor, and send time string
            chan.send("\033[u")
            chan.send(datetime.now().strftime("(%H:%M) "))

            # send "private" string
            if target:
                chan.send(f"*private (involves {', '.join(target)})* ")

            if context=="MESSAGE":
                chan.send(f"[{usercolor}] {msg}\r\n")
            if context=="JOIN":
                chan.send(f"{{LOG}} {usercolor} has joined!\r\n")
            if context=="EXIT":
                chan.send(f"{{LOG}} {usercolor} has exited!\r\n")
            if context=="PLAIN":
                chan.send(msg)

            # store new cursor position, and then set it back to the top line
            chan.send(f"\033[s\033[0;0f\033[K{chan._msg}")
        except:
            close_channel(chan)

def handle_user_input(chan):
    try:
        while True:
            chan._msg = ""
            while not chan._msg.endswith("\r"):
                transport = chan.recv(1024)

                # set cursor to 0, 0 and clear line
                chan.send("\033[0;0f\033[K")
                if transport == b"\x7f":
                    if len(chan._msg):
                        chan._msg = chan._msg[:-1]
                elif transport == b"\x04":
                    # interpret ctrl-d (EOF) as exit
                    chan._msg = "/exit"
                    break
                else:
                    chan._msg += transport.decode("utf-8")

                # send whole text, rotated for max 60 characters
                chan.send(chan._msg[-60:])

            chan.send("\033[0;0f\033[K")
            msg = chan._msg.strip()
            chan._msg = ""

            # USER / COMMANDS
            if msg.startswith("/exit"):
                break
            elif msg.startswith("/msg"):
                # check for correct usage
                if len(msg.split(" "))<3:
                    continue

                target = msg.split(" ")[1]
                tmsg   = " ".join(msg.split(" ")[2:])
                send_global(usercolor=chan._usernamecolor, target=[target, chan._username], msg=tmsg)
            elif msg.startswith("/status"):
                send_global(msg=build_status(chan), target=[chan._username], context="PLAIN")
            elif msg.startswith("/"):
                send_global(msg="\r\n/help to call this help\r\n/exit to exit\r\n/msg [username] [msg] to privatly message with a specified user\r\n/status to view a quick status", target=[chan._username], usercolor="*HELP*")

            elif msg:
                send_global(msg=msg, usercolor=chan._usernamecolor)
    except:
        pass
    close_channel(chan)

def close_channel(chan):
    # send EXIT message to everyone, excluding exiter
    chans.remove(chan)
    send_global(context="EXIT", usercolor=chan._usernamecolor)
    print(f"{chan._username} has left")

    try:
        # clear, and set cursor to 0,0
        chan.send("\033[2J\033[0;0f")
    except:
        pass
    chan.close()


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
    chan._msg = ""
    if not chan:
        print(f"No channel for {addr[0]}.")
        return

    chan._username = transport.get_username()
    chan._msg = ""
    print(f"User login: {chan._username}")
    chan._usernamecolor = USER_CFG[chan._username][1]+chan._username+COLOR_RESET
    chans.append(chan)

    # clear, and set cursor to 2,0 and store position
    chan.send(f"\033[2J\033[2;0fWelcome to {SERVER_NAME}!\r\n{build_status(chan)}\033[s")
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
