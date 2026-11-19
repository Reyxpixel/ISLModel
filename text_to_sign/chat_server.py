"""Chat relay between the two people in a conversation (Python version of Kunal's server.cpp).

    python text_to_sign/chat_server.py            # listens on port 8080
    python text_to_sign/chat_server.py --port 9000

Every message a client sends is passed on to every other connected client, exactly like
server.cpp, so Kunal's C++ client and chat_client.py can talk to each other.
"""
import argparse
import socket
import threading

clients = []
lock = threading.Lock()


def handle(conn, addr):
    print(f"[SERVER] {addr[0]}:{addr[1]} connected")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"[SERVER] {addr[1]}: {data.decode(errors='replace').strip()}")
            with lock:
                for other in clients:
                    if other is not conn:
                        try:
                            other.sendall(data)
                        except OSError:
                            pass
    except OSError:
        pass
    finally:
        with lock:
            if conn in clients:
                clients.remove(conn)
        conn.close()
        print(f"[SERVER] {addr[0]}:{addr[1]} disconnected")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", args.port))
    srv.listen()
    print(f"[SERVER] Listening on port {args.port}. Ctrl+C to stop.")
    srv.settimeout(1.0)  # lets Ctrl+C work on Windows
    try:
        while True:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            with lock:
                clients.append(conn)
            threading.Thread(target=handle, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[SERVER] Stopped.")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
