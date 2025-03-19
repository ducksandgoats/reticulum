import os
import signal
import sys
from http.server import BaseHTTPRequestHandler
import socketserver
import argparse
import mimetypes
import RNS

proxy_server = None

parser = argparse.ArgumentParser(
    description="Request web content from a Veilid server via DHT record."
)
parser.add_argument(
    "--identity",
    type=str,
    default="",
    help="Identity for you",
)
parser.add_argument(
    "--port",
    type=int,
    default=11010,
    help="Port to run the proxy server on (default: 9990)",
)
args = parser.parse_args()


def handle_exit(signum, frame):
    """Cleans up processes before exiting."""
    print("\n[Client] Shutting down...")
    if proxy_server:
        proxy_server.server_close()
        print("[Proxy] Proxy server stopped.")
    os._exit(0)


class ReticulumProxyHandler(BaseHTTPRequestHandler):
    """Handles incoming browser requests and routes them through Veilid."""

    def do_GET(self):
        """Handle HTTP GET requests"""
        self.req_and_res()

    def do_POST(self):
        """Handle HTTP POST requests"""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else None
        self.req_and_res(data=post_data)

    def determine_content_type(self):
        """Determine the content type based on file extension"""
        content_type = mimetypes.guess_type(self.path)[0]
        if content_type is None:
            # Default to text/html for unknown types
            content_type = "text/html"
        return content_type

    def request_failed(request_receipt):
        RNS.log("The request " + RNS.prettyhexrep(request_receipt.request_id) + " failed.")
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write("<html><head><title>Error</title></head><body><p>Error</p></body></html>".encode())

    def handle_response(self, request_receipt):
        raw_response = request_receipt.response
        response = RIPResponseObject()
        header = raw_response[0]
        header = header.split(" ", maxsplit=2)
        response.status = header[0]
        response.type = header[1]
        if len(header) > 2:
            response.meta = header[2]
        if raw_response[1]:
            response.body = raw_response[1]
        response.ok = True
        self.send_response(response.status)
        self.send_header("Content-type", self.determine_content_type(self.path))
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response.body)
        # try:
        #     self.send_response(response.status)
        #     self.send_header("Content-type", self.determine_content_type(self.path))
        #     self.send_header("Content-Length", str(len(response_bytes)))
        #     self.end_headers()
        #     self.wfile.write(response.body)
        # except Exception as e:
        #     print(f"[Proxy] Error sending response: {e}")
        #     self.send_response(400)
        #     self.send_header("Content-type", "text/html")
        #     self.end_headers()
        #     self.wfile.write("<html><head><title>Error</title></head><body><p>Error</p></body></html>".encode())

    def req_and_res(self, data=None):
        try:
            destination_hexhash = self.headers.get("X-Iden", "")
            if not destination_hexhash:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write("<html><head><title>Error</title></head><body><p>Error</p></body></html>".encode())
                return
            if len(destination_hexhash) != 32:
                RNS.log("Invalid destination entered. Check your input!\n")
            destination_hash = bytes.fromhex(destination_hexhash)
            if not RNS.Transport.has_path(destination_hash):
                RNS.log("Destination is not yet known. Requesting path and waiting for announce to arrive...")
                RNS.Transport.request_path(destination_hash)
            if destination_hexhash in dest and dest[destination_hexhash]['link']:
                RNS.log("Sending request to " + self.path)
                link = dest[destination_hexhash]['link']
                link.request(
                    self.path,
                    data=data,
                    response_callback=self.handle_response,
                    failed_callback=self.request_failed,
                    timeout=5,
                )
            else:
                def link_started(link):
                    RNS.log("Sending request to " + self.path)
                    dest[destination_hexhash]['link'] = link
                    link.request(
                        self.path,
                        data=data,
                        response_callback=self.handle_response,
                        failed_callback=self.request_failed,
                        timeout=5,
                    )
                def link_stopped(link):
                    if link.teardown_reason == RNS.Link.TIMEOUT:
                        RNS.log("The link timed out, exiting now")
                    elif link.teardown_reason == RNS.Link.DESTINATION_CLOSED:
                        RNS.log("The link was closed by the server, exiting now")
                    else:
                        RNS.log("Link closed, exiting now")
                    del dest[destination_hexhash]
                dest[destination_hexhash] = {'destination': None, 'link': None, 'link_started': link_started, 'link_stopped': link_stopped }
                server_identity = RNS.Identity.recall(destination_hash)
                RNS.log("Establishing link with server...")
                dest[destination_hexhash]['destination'] = RNS.Destination(
                    server_identity,
                    RNS.Destination.OUT,
                    RNS.Destination.SINGLE,
                    "rns",
                    "relay"
                )
                t_link = RNS.Link(dest[destination_hexhash]['destination'])
                t_link.set_link_established_callback(dest[destination_hexhash]['link_started'])
                t_link.set_link_closed_callback(dest[destination_hexhash]['link_stopped'])
        except Exception as e:
            print(f"[Proxy] Error sending response: {e}")
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write("<html><head><title>Error</title></head><body><p>Error</p></body></html>".encode())

def start_local_proxy(port, identify = None):
    """Starts a local HTTP proxy that routes requests through Reticulum."""
    RNS.Reticulum()
    global identity
    if identify:
        identity = identify
    else:
        identity = RNS.Identity()
    
    print("destination: ", RNS.Destination.hash(identity, "rns", "relay").hex())

    global proxy_server

    global dest
    dest = {}

    # Initialize mime types
    mimetypes.init()

    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Create and start the proxy server
    try:
        proxy_server = socketserver.TCPServer(("0.0.0.0", port), ReticulumProxyHandler)
        print(f"[Client] Local proxy server running at http://localhost:{port}")
        print("[Client] Press Ctrl+C to exit")
        proxy_server.serve_forever()
    except KeyboardInterrupt:
        handle_exit(None, None)
    except Exception as e:
        print(f"[Client] Error starting proxy server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_local_proxy(args.port, args.identity)
