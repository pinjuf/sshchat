# SSHChat
## A chatroom server that runs over SSH

> This code is still in it's earliest stages, and still lacks a lot.
> 
>  At this point, it's really nothing more than a sketch.

### Setting up
Install the requirements:

```pip3 install -r requirements.txt```

The code requires an RSA private key, named `rsa.private`.
> The filename can be easily changed in the config part of the code!

To generate such a key, you could (for example) use OpenSSL:

```openssl genrsa -out rsa.private 1024```

### Running the server
To run, simply execute `sshchat.py`.

Now users can connect to it over SSH (standard port is 2222). When logging in for the first time, they must enter a password, which they must use if they wish to login with the same username again. Passwords are reset each runtime.

User can now send messages by typing text and using backspace to correct mistakes.

To leave, a user must type `/exit` or send an EOF (Ctrl-D).
