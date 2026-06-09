import logging
import socket
from agent.runner import run_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Prevent piazza-api (and any other requests) from hanging indefinitely
socket.setdefaulttimeout(30)

if __name__ == "__main__":
    run_all()
