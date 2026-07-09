import socket
import requests

def tcp_ping(host, port, timeout=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()

def http_ok(url):
    return requests.get(url, timeout=5).status_code == 200
