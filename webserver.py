import socket
import threading
import os
from datetime import datetime

# Konfigurasi Server (Ganti HOST dengan IP LAN Anda jika uji coba beda laptop)
HOST = '0.0.0.0'
TCP_PORT = 8001
UDP_PORT = 9002

# ==========================================
# MIME TYPES
# FIX BUG UTAMA: Content-Type harus nyesuain ekstensi file,
# bukan hardcode text/html. Browser (standards mode) nolak
# stylesheet kalau Content-Type-nya bukan text/css.
# ==========================================
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.htm':  'text/html; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.svg':  'image/svg+xml',
    '.ico':  'image/x-icon',
    '.mp4':  'video/mp4',
    '.webm': 'video/webm',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.txt':  'text/plain; charset=utf-8',
}

def get_content_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    return MIME_TYPES.get(ext, 'application/octet-stream')


def build_response(status_line, content, content_type):
    """Bangun HTTP response (header + body) secara konsisten."""
    response = f"HTTP/1.1 {status_line}\r\n".encode('utf-8')
    response += f"Content-Type: {content_type}\r\n".encode('utf-8')
    response += f"Content-Length: {len(content)}\r\n".encode('utf-8')
    response += b"Connection: close\r\n\r\n"
    response += content
    return response


def load_error_page(code, fallback_message):
    """
    Ambil halaman error dari folder status/ (mis. status/404.html).
    Kalau filenya nggak ada, pakai HTML inline sederhana sebagai cadangan.
    """
    path = os.path.join('status', f'{code}.html')
    if os.path.isfile(path):
        with open(path, 'rb') as f:
            return f.read()
    return (f"<html><body><h1>{code}</h1>"
            f"<p>{fallback_message}</p></body></html>").encode('utf-8')


# ==========================================
# BAGIAN 1: FUNGSI UNTUK MENANGANI TCP HTTP
# ==========================================
def handle_tcp_client(client_socket, client_address):
    client_socket.settimeout(5)
    try:
        # Menerima request dari client/proxy
        request = client_socket.recv(1024).decode('utf-8')
        if not request:
            return

        # Mengambil baris pertama dari HTTP Request (misal: "GET /index.html HTTP/1.1")
        headers = request.split('\r\n')
        request_line = headers[0].split()

        if len(request_line) > 1:
            method = request_line[0]
            path = request_line[1]

            # Membersihkan tanda '/' di depan nama file
            filename = path.lstrip('/')

            # Jika user hanya memanggil IP:Port/, berikan file default
            # FIX BUG 2: disamakan dengan proxy (index.html), bukan HelloWorld.html
            if filename == '':
                filename = 'index.html'

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Cek apakah file ada di direktori
            if os.path.isfile(filename):
                status_code = "200 OK"
                with open(filename, 'rb') as f:
                    content = f.read()

                # FIX BUG UTAMA: Content-Type ikut ekstensi file
                content_type = get_content_type(filename)
                response = build_response("200 OK", content, content_type)
                client_socket.sendall(response)

            else:
                # 404 Not Found -> sajikan dari status/404.html bila ada
                status_code = "404 Not Found"
                body = load_error_page(404, "File tidak ditemukan di server.")
                response = build_response("404 Not Found", body, "text/html; charset=utf-8")
                client_socket.sendall(response)

            print(f"[TCP LOG] IP: {client_address[0]} | File: /{filename} | Waktu: {timestamp} | Status: {status_code}")

        else:
            # Request tidak valid / malformed
            # FIX BUG 3 & 6: tambah 500 Internal Server Error
            raise ValueError("Malformed HTTP request line")

    except ValueError as e:
        # FIX BUG 3: Handle malformed request -> 500
        print(f"[TCP ERROR] Request tidak valid dari {client_address[0]}: {e}")
        try:
            body = load_error_page(500, "Request tidak valid.")
            response = build_response("500 Internal Server Error", body, "text/html; charset=utf-8")
            client_socket.sendall(response)
        except:
            pass
    except Exception as e:
        # FIX BUG 3 & 6: Semua exception lain -> 500 dengan response yang proper
        print(f"[TCP ERROR] Terjadi kesalahan dari {client_address[0]}: {e}")
        try:
            body = load_error_page(500, "Terjadi kesalahan internal.")
            response = build_response("500 Internal Server Error", body, "text/html; charset=utf-8")
            client_socket.sendall(response)
        except:
            pass
    finally:
        client_socket.close()


def start_tcp_server():
    # Membuat socket TCP (SOCK_STREAM)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, TCP_PORT))
    server_socket.listen(5)

    print(f"[TCP SERVER] Berjalan dan mendengarkan di http://{HOST}:{TCP_PORT}")

    while True:
        client_socket, client_address = server_socket.accept()
        # Membuat thread baru untuk setiap client HTTP yang terkoneksi
        client_thread = threading.Thread(target=handle_tcp_client, args=(client_socket, client_address))
        client_thread.daemon = True
        client_thread.start()


# ==========================================
# BAGIAN 2: FUNGSI UNTUK MENANGANI UDP ECHO
# ==========================================
def start_udp_server():
    # Membuat socket UDP (SOCK_DGRAM)
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((HOST, UDP_PORT))
    print(f"[UDP SERVER] Berjalan di port {UDP_PORT} (Mode Echo)")

    while True:
        # Menerima paket dari client
        message, client_address = udp_socket.recvfrom(1024)
        print(f"[UDP] Menerima paket ping dari {client_address}, memantulkan kembali...")
        # Mengirimkan pesan yang sama persis kembali ke client
        udp_socket.sendto(message, client_address)


# ==========================================
# PROGRAM UTAMA: MENJALANKAN KEDUA SERVER
# ==========================================
if __name__ == "__main__":
    print("=== MEMULAI WEB SERVER ===")

    # Menyiapkan Thread untuk TCP dan UDP
    tcp_thread = threading.Thread(target=start_tcp_server)
    tcp_thread.daemon = True

    udp_thread = threading.Thread(target=start_udp_server)
    udp_thread.daemon = True

    # Menjalankan kedua Thread
    tcp_thread.start()
    udp_thread.start()

    # Menjaga program utama tetap hidup sampai user menekan Ctrl+C
    # FIX: pakai Event.wait() biar nggak busy-loop (CPU 100%)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nMematikan server...")

        