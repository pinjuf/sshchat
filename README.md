# SSHChat
## A chatroom server that runs over SSH

> This code is still in it's earliest stages, and still lacks a lot.
> 
>  At this point, it's really nothing more than a sketch.

### Setting up
Install the requirements:

```pip3 install -r requirements.txt```

The code requires an RSA private key, named `rsa.private`.
> The filename can be easily changed using command line options or the config part of the code!

A demo key is included. To generate such a key, you could (for example) use OpenSSL:

```openssl genrsa -out rsa.private 1024```

### Running the server
I recommend having a quick look at the options: `./sshchat.py -h`. The verbose option can also be useful for basic troubleshooting.

To run, simply execute `sshchat.py`.

Now users can connect to it over SSH (standard port is 2222). When logging in for the first time, they must enter a password, which they must use if they wish to login with the same username again. Passwords are stored in a pickle file.
> Note that an interactive SSH session is necesarry.

User can now send messages by typing text and using backspace to correct mistakes.

To leave, a user must type `/exit` or send an EOF (Ctrl-D).
