import socket
import time
import sys
import argparse
import math

PROXY_HOST = '10.169.91.44'
PROXY_PORT = 8081      # TCP: Client HTTP wajib lewat Proxy
UDP_SERVER_HOST = '10.169.91.1'
UDP_SERVER_PORT = 9002 # UDP: Client QoS langsung ke Web Server

BUFFER_SIZE = 4096

def mode_http_tcp():
    print("\n--- Mode HTTP (TCP) via Proxy ---")
    file_path = input("Masukkan file yang direquest (contoh: /index.html) : ")
    
    if not file_path.startswith('/'):
        file_path = '/' + file_path

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((PROXY_HOST, PROXY_PORT))
        print(f"[CLIENT] Terhubung ke Proxy {PROXY_HOST}:{PROXY_PORT}")
        
        request = f"GET {file_path} HTTP/1.1\r\nHost: {PROXY_HOST}\r\nConnection: close\r\n\r\n"
        print("\n[CLIENT] Mengirim Request:")
        print(request.strip())
        
        client_socket.sendall(request.encode('utf-8'))
        
        response_data = b""
        while True:
            chunk = client_socket.recv(BUFFER_SIZE)
            if not chunk:
                break
            response_data += chunk
            
        print("\n[CLIENT] Menerima Response:")
        print(response_data.decode('utf-8', errors='ignore'))
        
    except Exception as e:
        print(f"[CLIENT] Error saat mode HTTP: {e}")
    finally:
        client_socket.close()

def mode_qos_udp():
    print("\n--- Mode Analisis QoS (UDP) ---")
    try:
        num_packets_str = input("Berapa paket yang ingin dikirim? (Tekan enter untuk default 10) : ")
        if num_packets_str.strip() == "":
            num_packets = 10
        else:
            num_packets = int(num_packets_str)
            if num_packets < 10:
                print("[INFO] Jumlah terlalu sedikit. Diganti menjadi 10 paket.")
                num_packets = 10
    except ValueError:
        print("[INFO] Input tidak valid. Menggunakan default 10 paket.")
        num_packets = 10

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(1.0)

    rtt_list = []
    packets_received = 0
    total_bytes_received = 0
    
    print(f"\n[CLIENT] Memulai pengiriman {num_packets} paket UDP ke {UDP_SERVER_HOST}:{UDP_SERVER_PORT}...")
    
    start_time_total = time.time()

    for seq in range(1, num_packets + 1):
        send_time = time.time()
        message = f"Ping {seq} {send_time}"
        
        try:
            client_socket.sendto(message.encode('utf-8'), (UDP_SERVER_HOST, UDP_SERVER_PORT))
            
            data, server = client_socket.recvfrom(BUFFER_SIZE)
            receive_time = time.time()
            
            rtt_ms = (receive_time - send_time) * 1000
            rtt_list.append(rtt_ms)
         
            print(f"Reply dari {server[0]}: seq={seq} time={rtt_ms:.2f} ms payload=\"{data.decode('utf-8')}\"")
        
        except socket.timeout:
            print(f"Request timeout untuk seq={seq}")

    end_time_total = time.time()
    packets_received += 1
    total_bytes_received += {data}
    
    print("\n==========================================")
    print("            HASIL ANALISIS QoS")
    print("==========================================")
    
    if packets_received > 0:
        # 1. RTT (Round Trip Time)
        min_rtt = min(rtt_list)
        max_rtt = max(rtt_list)
        avg_rtt = sum(rtt_list) / len(rtt_list)
        print(f"RTT        : Min = {min_rtt:.2f} ms | Max = {max_rtt:.2f} ms | Rata-rata = {avg_rtt:.2f} ms")
        
        # FIX BUG 7: Jitter = standard deviation dari selisih RTT (sesuai spec PDF hal.13)
        if len(rtt_list) > 1:
            delta_rtt_list = [rtt_list[i] - rtt_list[i-1] for i in range(1, len(rtt_list))]
            mean_delta = sum(delta_rtt_list) / len(delta_rtt_list)
            variance = sum((d - mean_delta) ** 2 for d in delta_rtt_list) / len(delta_rtt_list)
            jitter = math.sqrt(variance)
        else:
            jitter = 0.0
        print(f"Jitter     : {jitter:.2f} ms")
        
        total_time_seconds = end_time_total - start_time_total
        throughput_bps = (total_bytes_received * 8) / total_time_seconds if total_time_seconds > 0 else 0
        print(f"Throughput : {throughput_bps / 1000:.2f} kbps ({total_bytes_received} bytes dalam {total_time_seconds:.4f} detik)")
    else:
        print("RTT, Jitter, dan Throughput tidak dapat dihitung karena tidak ada paket yang diterima.")

    packet_loss_percent = ((num_packets - packets_received) / num_packets) * 100
    print(f"Packet Loss: {packet_loss_percent:.1f}% ({packets_received}/{num_packets} paket berhasil diterima)")
    print("==========================================")


def menu_interaktif():
    while True:
        print("\n==========================================")
        print("       PROGRAM CLIENT MULTI-MODE")
        print("==========================================")
        print("Pilih mode operasi:")
        print("1. Mode HTTP (TCP) -> Akses Web via Proxy")
        print("2. Mode QoS (UDP)  -> Uji Pinger ke Server")
        print("3. Keluar")
        
        pilihan = input("Masukkan pilihan (1/2/3) : ")
        
        if pilihan == '1':
            mode_http_tcp()
        elif pilihan == '2':
            mode_qos_udp()
        elif pilihan == '3':
            print("Terima kasih. Program ditutup.")
            sys.exit(0)
        else:
            print("Pilihan tidak valid, silakan coba lagi.")

def main():
    parser = argparse.ArgumentParser(description="Client Jaringan Komputer (TCP/UDP)")
    parser.add_argument('-mode', type=str, choices=['tcp', 'udp'], help="Pilih mode: tcp (untuk HTTP proxy) atau udp (untuk QoS)")
    
    args = parser.parse_args()
    
    if args.mode == 'tcp':
        mode_http_tcp()
    elif args.mode == 'udp':
        mode_qos_udp()
    else:
        menu_interaktif()

if __name__ == "__main__":
    main()
