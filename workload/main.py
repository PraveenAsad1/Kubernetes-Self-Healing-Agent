import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get('PORT', 8080))

memory_hog = []

def allocate_memory():
    print("Starting rapid memory allocation...")
    try:
        while True:
            # Allocate roughly 10MB chunks repeatedly
            memory_hog.append(' ' * 10 * 1024 * 1024)
            print(f"Allocated {len(memory_hog) * 10} MB so far...")
            time.sleep(0.1)
    except Exception as e:
        print(f"Error during allocation: {e}")

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/crash':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Crashing initiated...\n")
            
            # Start allocation in a background thread so we can return response
            t = threading.Thread(target=allocate_memory)
            t.daemon = True
            t.start()
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK\n")
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('', PORT), RequestHandler)
    print(f"Starting memory-hog workload on port {PORT}...")
    server.serve_forever()
