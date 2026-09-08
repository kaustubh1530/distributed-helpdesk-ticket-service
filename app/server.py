from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class TicketRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/health":

            response = {
                "node_name": "ticket-server",
                "role": "single-server",
                "status": "healthy"
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(
                json.dumps(response).encode("utf-8")
            )

        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            response = {
                "error": "Endpoint not found"
            }

            self.wfile.write(
                json.dumps(response).encode("utf-8")
            )


def run_server():
    server_address = ("localhost", 8000)

    httpd = HTTPServer(server_address, TicketRequestHandler)

    print("Ticket server running at http://localhost:8000")
    print("Health check: http://localhost:8000/health")

    httpd.serve_forever()


if __name__ == "__main__":
    run_server()