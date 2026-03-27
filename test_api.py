import requests

def test_port(port):
    url = f"http://localhost:{port}/kabusapi/auth"
    print(f"Testing Port {port}...")
    try:
        response = requests.get(url, timeout=5)
        print(f"  [SUCCESS] Port {port} responded!")
        print(f"  Status Code: {response.status_code}")
        print(f"  Headers: {response.headers}")
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Port {port} is NOT reachable (ConnectionError).")
    except Exception as e:
        print(f"  [SUCCESS?] Port {port} responded with exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_port(8080)
    test_port(8081)
