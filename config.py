#!/usr/bin/env python3
import os

USER_CFG_PATH = os.path.join("data", "usercfg.data")
BLACKLIST_PATH = os.path.join("cfg", "blacklist.txt")
RSA_PATH = os.path.join("cfg", "rsa.private")
BIND_IP = ""
PORT = 2222
SERVER_NAME = "ASDFroom"
VERBOSE = False

COLORS = [
    "\x1b[31m",
    "\x1b[32m",
    "\x1b[33m",
    "\x1b[34m",
    "\x1b[35m",
    "\x1b[36m",
    "\x1b[37m",
    ]

COLOR_RESET = "\x1b[0m"
