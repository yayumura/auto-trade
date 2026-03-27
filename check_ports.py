import psutil

def check_all_listen_ports():
    print("--- Searching for ALL LISTEN ports on this system ---")
    try:
        connections = psutil.net_connections(kind='inet')
        found = False
        for conn in connections:
            if conn.status == 'LISTEN':
                found = True
                laddr = f"{conn.laddr.ip}:{conn.laddr.port}"
                try:
                    process = psutil.Process(conn.pid)
                    proc_name = process.name()
                except:
                    proc_name = "Unknown"
                
                print(f"  - Port: {conn.laddr.port:5} | Local: {laddr:20} | Process: {proc_name} (PID: {conn.pid})")
        
        if not found:
            print("No LISTEN ports found (Check if running as Admin).")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_all_listen_ports()
