from http.server import BaseHTTPRequestHandler, HTTPServer
import json


# In-memory ticket storage
tickets = []

# Simple ticket ID counter
next_ticket_id = 1


class TicketRequestHandler(BaseHTTPRequestHandler):

    def send_json_response(self, status_code, response):
        """Send a JSON response to the client."""

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(
            json.dumps(response).encode("utf-8")
        )

    def do_GET(self):
        """Handle GET requests."""

        if self.path == "/health":

            response = {
                "node_name": "ticket-server",
                "role": "single-server",
                "status": "healthy"
            }

            self.send_json_response(200, response)

        elif self.path == "/tickets":

            response = {
                "tickets": tickets
            }

            self.send_json_response(200, response)

        else:

            response = {
                "error": "Endpoint not found"
            }

            self.send_json_response(404, response)

    def do_POST(self):
        """Handle POST requests."""

        global next_ticket_id

        if self.path == "/tickets":

            # Read request body
            content_length = int(
                self.headers.get("Content-Length", 0)
            )

            request_body = self.rfile.read(content_length)

            try:
                data = json.loads(request_body.decode("utf-8"))

            except json.JSONDecodeError:

                response = {
                    "error": "Invalid JSON"
                }

                self.send_json_response(400, response)
                return

            # Validate required field
            title = data.get("title")

            if not title:

                response = {
                    "error": "Ticket title is required"
                }

                self.send_json_response(400, response)
                return

            # Create ticket
            ticket = {
                "ticket_id": next_ticket_id,
                "title": title,
                "status": "open"
            }

            tickets.append(ticket)

            next_ticket_id += 1

            # Return created ticket
            self.send_json_response(201, ticket)

        else:

            response = {
                "error": "Endpoint not found"
            }

            self.send_json_response(404, response)


def run_server():

    server_address = ("localhost", 8000)

    httpd = HTTPServer(
        server_address,
        TicketRequestHandler
    )

    print("Ticket server running at http://localhost:8000")
    print("Health check: http://localhost:8000/health")
    print("Tickets: http://localhost:8000/tickets")

    httpd.serve_forever()


if __name__ == "__main__":
    run_server()