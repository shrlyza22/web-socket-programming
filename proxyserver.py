import socket
import sys
import threading
import os
import time

# Configuration
# FIX: Sesuaikan IP ini dengan IP laptop Web Server di jaringan LAN/hotspot
WEB_SERVER_HOST = '10.169.91.1'  # <-- GANTI dengan IP laptop Web Server
WEB_SERVER_PORT = 8001
PROXY_HOST = '0.0.0.0'
PROXY_PORT = 8081
BUFFER_SIZE = 4096
WEB_SERVER_TIMEOUT = 10  # FIX BUG 4: timeout koneksi ke web server (detik)

# FIX BUG 5: Lock untuk mencegah race condition saat tulis cache bersamaan
cache_lock = threading.Lock()

def handle_client(client_socket, client_address):
    start_time = time.time()
    web_socket = None  # FIX: inisialisasi agar bisa di-close di finally
    
    try:
        # 1. Terima request dari client
        request_data = client_socket.recv(BUFFER_SIZE)
        if not request_data:
            client_socket.close()
            return

        # Parsing request HTTP
        request_str = request_data.decode('utf-8', errors='ignore')
        first_line = request_str.split('\n')[0]
        url = first_line.split(' ')[1]
        
        # FIX BUG 2: default filename disamakan dengan webserver (index.html)
        filename = url.lstrip('/')
        if filename == '':
            filename = 'index.html'
        
        cache_filename = "cache_" + filename.replace('/', '_')
        
        # 2. Logika File-Based Caching
        cache_status = ""
        
        if os.path.exists(cache_filename):
            # CACHE HIT: File sudah ada di penyimpanan lokal proxy
            cache_status = "HIT"
            with open(cache_filename, 'rb') as f:
                response_data = f.read()
            client_socket.sendall(response_data)
            
        else:
            # CACHE MISS: File belum ada, harus minta ke Web Server
            cache_status = "MISS"
            
            # Buka koneksi baru ke Web Server
            web_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # FIX BUG 4: set timeout agar tidak hang selamanya
            web_socket.settimeout(WEB_SERVER_TIMEOUT)
            web_socket.connect((WEB_SERVER_HOST, WEB_SERVER_PORT))
            web_socket.sendall(request_data)
            
            # Terima balasan dari Web Server
            response_data = b""
            while True:
                chunk = web_socket.recv(BUFFER_SIZE)
                if len(chunk) == 0:
                    break
                response_data += chunk
            
            web_socket.close()
            web_socket = None
            
            # --- PERBAIKAN DI SINI ---
            # Cek apakah response valid (HTTP Status 200 OK) sebelum di-cache
            is_successful_response = False
            try:
                # Decode bagian awal response untuk membaca Status Line
                response_str = response_data.decode('utf-8', errors='ignore')
                status_line = response_str.split('\r\n')[0]
                
                # Hanya simpan ke cache jika statusnya "200 OK"
                if "HTTP/" in status_line and "200 OK" in status_line:
                    is_successful_response = True
                else:
                    cache_status = "MISS (NOT CACHED - SERVER ERROR/NOT FOUND)"
            except Exception:
                # Jika gagal parsing, cari aman dengan tidak menyimpan ke cache
                is_successful_response = False

            # FIX BUG 5: Gunakan lock saat tulis cache untuk cegah race condition
            if is_successful_response:
                with cache_lock:
                    if not os.path.exists(cache_filename):  # Double-check setelah dapat lock
                        with open(cache_filename, 'wb') as f:
                            f.write(response_data)
            # -------------------------
            
            # Teruskan balasan ke client (tetap diteruskan meskipun statusnya error)
            client_socket.sendall(response_data)

        # Hitung waktu selesai
        end_time = time.time()
        response_time = (end_time - start_time) * 1000
        print(f"[LOG] IP: {client_address[0]} | URL: {url} | Cache: {cache_status} | Waktu: {response_time:.2f} ms")

    except socket.timeout:
        # FIX BUG 4: timeout -> 504 Gateway Timeout (bukan 502)
        print(f"[ERROR] Timeout menghubungi Web Server untuk request dari {client_address[0]}")
        try:
            error_msg = "HTTP/1.1 504 Gateway Timeout\r\nContent-Type: text/html\r\nContent-Length: 76\r\n\r\n<html><body><h1>504 Gateway Timeout</h1><p>Web Server tidak merespons.</p></body></html>"
            client_socket.sendall(error_msg.encode('utf-8'))
        except:
            pass

    except ConnectionRefusedError:
        # Web Server tidak bisa dihubungi -> 502 Bad Gateway
        print(f"[ERROR] Web Server tidak dapat dihubungi (Connection Refused) dari {client_address[0]}")
        try:
            error_msg = "HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/html\r\nContent-Length: 74\r\n\r\n<html><body><h1>502 Bad Gateway</h1><p>Web Server sedang down.</p></body></html>"
            client_socket.sendall(error_msg.encode('utf-8'))
        except:
            pass

    except Exception as e:
        print(f"[ERROR] Proxy gagal memproses request dari {client_address[0]}: {e}")
        try:
            error_msg = "HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/html\r\nContent-Length: 74\r\n\r\n<html><body><h1>502 Bad Gateway</h1><p>Web Server sedang down.</p></body></html>"
            client_socket.sendall(error_msg.encode('utf-8'))
        except:
            pass
        
    finally:
        if web_socket:
            try:
                web_socket.close()
            except:
                pass
        client_socket.close()

def main():
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        proxy_socket.bind((PROXY_HOST, PROXY_PORT))
        proxy_socket.listen(100)
        print(f"==========================================")
        print(f"[PROXY] Started running on {PROXY_HOST}:{PROXY_PORT}")
        print(f"[PROXY] Forwarding ke Web Server: {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
        print(f"[PROXY] Waiting for client connections...")
        print(f"==========================================")
        
        while True:
            client_socket, client_address = proxy_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            client_thread.daemon = True
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\n[PROXY] Shutting down proxy server gracefully...")
    except Exception as e:
        print(f"[PROXY] Critical Error: {e}")
    finally:
        proxy_socket.close()
        sys.exit(0)

if __name__ == "__main__":
    main()