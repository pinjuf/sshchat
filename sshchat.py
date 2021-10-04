#!/usr/bin/env python3
import logging
import socket
import threading
import random
import hashlib
import argparse
import pickle
import os
import sys
from datetime import datetime

import paramiko

COLORS = [
    "\033[31m",
    "\033[32m",
    "\033[33m",
    "\033[34m",
    "\033[35m",
    "\033[36m",
    "\033[37m",
    ]

COLOR_RESET = "\033[0m"

chans = []

# DEFAULT CONFIG

USER_CFG_PATH = os.path.join("data", "usercfg.data")
BLACKLIST_PATH = os.path.join("cfg", "blacklist.txt")
RSA_PATH = os.path.join("cfg", "rsa.private")
BIND_IP = ""
PORT = 2222
SERVER_NAME = "ASDFroom"
VERBOSE = False

# CFG END

CHATHELPMSG = ("\r\n[HELP]\r\n"
               "/help to call this help\r\n"
               "/clear clears your screen (e.g. if the host fucked up)\r\n"
               "/exit to exit\r\n"
               "/msg [username] [msg] to privatly message a specified user\r\n"
               "/status to view a quick status"
               "\r\n/passwd <new password> to set your password\r\n"
              )

def usage():
    return (
           "Py. SSHChat HELP\r\n\r\n"
           "INFO:\r\n"
           "\tSSHChat allows for hosting chatrooms which are accessible over SSH.\r\n"
           "\tIt is written completely in Python 3.\r\n"
           )

def insertat(string, char, i):
    return string[:i] + char + string[i:]

class ChatRoomServ(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        # if user's first login, register with entered password (stored as sha256)
        if not username in USER_CFG.keys():
            USER_CFG[username] = [hashlib.sha256(password.encode()).digest(), random.choice(COLORS)]

            # store data
            with open(USER_CFG_PATH, "wb") as picklefile:
                pickle.dump(USER_CFG, picklefile)

            return paramiko.AUTH_SUCCESSFUL

        if USER_CFG[username][0] == hashlib.sha256(password.encode()).digest():
            return paramiko.AUTH_SUCCESSFUL

        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_pty_request(self, *_): # yeah i don t care, just do it
        return True

class UserClass:
    msg = ""
    username = "???"
    usernamecolor = username
    chan = None
    cursorpos = 0

def build_status(userchan):
    return (f"\r\n[CHATROOM STATUS]\r\n"
            f"Server name: {SERVER_NAME}\r\n"
            f"Currently {len(chans)} user(s) online.\r\n"
            f"Your username: [{userchan.usernamecolor}]\r\n"
           )

def send_global(msg="", context="MESSAGE", usercolor="???", target=False):
    global is_sending_global
    while is_sending_global: # wait for other sendings to finish
        pass
    is_sending_global = True

    if target:
        target = list(dict.fromkeys(target))
    for usersc in chans.copy():
        try:
            # check if user is targeted
            if target and usersc.username not in target:
                continue

            # reset cursor, and send time string
            usersc.chan.send("\033[u")
            usersc.chan.send(datetime.now().strftime("(%H:%M) "))

            # send "private" string
            if target:
                usersc.chan.send(f"*private (involves {', '.join(target)})* ")

            if context=="MESSAGE":
                usersc.chan.send(f"[{usercolor}] {msg}\r\n")
            if context=="JOIN":
                usersc.chan.send(f"{{LOG}} {usercolor} has joined!\r\n")
            if context=="EXIT":
                usersc.chan.send(f"{{LOG}} {usercolor} has exited!\r\n")
            if context=="PLAIN":
                usersc.chan.send(msg)

            # store new cursor position, and then set it back to the top line
            usersc.chan.send(f"\033[s\033[0;0f\033[K{usersc.msg}")
        except Exception as ex:
            logger.log(logging.INFO, ex)
            close_channel(usersc)

    is_sending_global = False

def handle_user_input(usersc):
    try:
        while True:
            usersc.msg = ""
            usersc.cursorpos = 0
            while True:
                transport = usersc.chan.recv(1024)
                # set cursor to 0, 0 and clear line
                usersc.chan.send("\033[0;0f\033[K")
                if transport == b"\x7f":
                    if usersc.cursorpos:
                        usersc.msg = usersc.msg[:usersc.cursorpos-1] + usersc.msg[usersc.cursorpos:]
                        usersc.cursorpos -= 1

                elif transport in [b"\r", b"\n", b"\r\n"]:
                    usersc.msg += transport.decode("utf-8", errors="replace")
                    break

                elif transport == b"\033[D":
                    if usersc.cursorpos:
                        usersc.cursorpos -=1
                elif transport == b"\033[C":
                    if usersc.cursorpos < len(usersc.msg):
                        usersc.cursorpos +=1

                elif transport == b"\x04":
                    # interpret ctrl-d (EOF) as exit
                    usersc.msg = "/exit"
                    break
                else:
                    usersc.msg = insertat(usersc.msg,
                                          transport.decode("utf-8", errors="replace"),
                                          usersc.cursorpos)
                    usersc.cursorpos += 1

                # send whole text, rotated for max 60 characters
                usersc.chan.send(usersc.msg[-60:] + f"\033[0;{usersc.cursorpos+1}f")

            usersc.chan.send("\033[0;0f\033[K")
            msg = usersc.msg.strip()
            usersc.msg = ""

            # USER / COMMANDS
            if msg.startswith("\""):
                msg = msg[1:]
                send_global(msg=msg, usercolor=usersc.usernamecolor)

            elif msg.startswith("/exit"):
                break

            elif msg.startswith("/clear"):
                usersc.chan.send("\033[2J\033[2;0f\033[s\033[0;0f")

            elif msg.startswith("/msg") and len(msg.split())>=3:
                target = msg.split()[1]
                tmsg   = msg.split(maxsplit=2)[2] 
                send_global(usercolor=usersc.usernamecolor,
                            target=[target, usersc.username], msg=tmsg)

            elif msg.startswith("/status"):
                send_global(msg=build_status(usersc), target=[usersc.username], context="PLAIN")

            elif msg.startswith("/passwd"):
                new_passwd = "" if len(msg.split())<2 else " ".join(msg.split()[1:])
                USER_CFG[usersc.username][0] = hashlib.sha256(new_passwd.encode()).digest()

                 # store data
                with open(USER_CFG_PATH, "wb") as picklefile:
                    pickle.dump(USER_CFG, picklefile)
                send_global(msg="\r\n[PASSWD]\r\nYour password has been set.\r\n",
                            target=[usersc.username], context="PLAIN")

            elif msg.startswith("/"):
                send_global(msg=CHATHELPMSG, target=[usersc.username], context="PLAIN")

            elif msg:
                send_global(msg=msg, usercolor=usersc.usernamecolor)

    except Exception as ex:
        logger.log(logging.INFO, ex)
    close_channel(usersc)

def close_channel(usersc):
    # send EXIT message to everyone, excluding exiter
    try:
        chans.remove(usersc)
        send_global(context="EXIT", usercolor=usersc.usernamecolor)
        logger.log(logging.INFO, f"{usersc.username} has left")

        # clear, and set cursor to 0,0
        usersc.chan.send("\033[2J\033[0;0f")
    except Exception as ex:
        logger.log(logging.INFO, f"Error during closing of channel. ({ex})")
    usersc.chan.close()


def init_user(ca_pair):
    client, addr = ca_pair
    logger.log(logging.INFO, f"Connection from {addr[0]}!")

    transport = paramiko.Transport(client)
    transport.add_server_key(host_key)

    server = ChatRoomServ()
    try:
        transport.start_server(server=server)
    except Exception as ex:
        logger.log(logging.INFO, f"SSH negotiation failed for {addr[0]} failed. ({ex})")
        return

    chan = transport.accept()
    if not chan:
        logger.log(logging.INFO, f"No channel for {addr[0]}.")
        return

    server.event.wait(10)
    if not server.event.is_set():
        logger.log(logging.INFO, f"{addr[0]} never asked for a shell")
        return

    usersc = UserClass()
    usersc.chan = chan
    usersc.username = transport.get_username()
    usersc.usernamecolor = USER_CFG[usersc.username][1]+usersc.username+COLOR_RESET
    chans.append(usersc)
    logger.log(logging.INFO, f"User login: {usersc.username}")

    # clear, and set cursor to 2,0 and store position, before sending welcome msg
    usersc.chan.send(f"\033[2J\033[2;0fWelcome to {SERVER_NAME}!\r\n"
              f"Try typing /help!{build_status(usersc)}\033[s"
             )
    send_global(context="JOIN", usercolor=usersc.usernamecolor)
    handle_user_input(usersc)


def run_chatroom():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((BIND_IP, PORT))
    sock.listen(128)

    while True:
        try:
            conn, addr = sock.accept()
            if addr[0] in BLACKLIST:
                conn.close()
                logger.log(logging.INFO, f"Refused connection from {ca_pair[1][0]} (blacklist)")
                continue

            threading.Thread(target=init_user, args=((conn, addr),)).start()
        except Exception as ex:
            if stopped:
                break

argparser = argparse.ArgumentParser(usage=usage())

argparser.add_argument("-v", "--verbose", default=VERBOSE, action="store_true", help="verbose")
argparser.add_argument("-b", "--bindip", default=BIND_IP, help="Binding IP")
argparser.add_argument("-p", "--port", type=int, default=PORT, help="SSH Server port")
argparser.add_argument("-n", "--name", type=str, default=SERVER_NAME, help="Server name")
argparser.add_argument("-r", "--rsafile", type=str, default=RSA_PATH, help="RSA file")
argparser.add_argument("-k", "--blacklist", type=str, default=BLACKLIST_PATH, help="IP Blacklist")
argparser.add_argument("-d", "--data", type=str, default=USER_CFG_PATH, help="Pickle data file")

args = argparser.parse_args()

BIND_IP = args.bindip
PORT = args.port
SERVER_NAME = args.name
RSA_PATH = args.rsafile
USER_CFG_PATH = args.data
VERBOSE = args.verbose
BLACKLIST_PATH = args.blacklist

host_key = paramiko.RSAKey.from_private_key_file(filename=RSA_PATH)

if os.path.exists(USER_CFG_PATH):
    with open(USER_CFG_PATH, "rb") as file:
        USER_CFG = pickle.load(file)
else:
    USER_CFG = {}

if os.path.exists(BLACKLIST_PATH):
    with open(BLACKLIST_PATH, "r") as file:
        BLACKLIST = [ip.strip() for ip in file.readlines()]
else:
    BLACKLIST = []

logging.basicConfig(level=logging.INFO if VERBOSE else logging.WARNING)
logger = logging.getLogger()
logger.log(logging.INFO, f"Starting chatroom {SERVER_NAME} on port {PORT}!")

threading.Thread(target=run_chatroom).start()

stopped = False
is_sending_global = False

while True:
    try:
        pass
    except KeyboardInterrupt:
        logger.log(logging.INFO, f"Received KeyboardInterrupt, stopping!")
        stopped = True
        break

sys.exit()
