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

            self.send_json_response(
                404,
                {"error": "Endpoint not found"}
            )

    def do_POST(self):
        """Handle POST requests."""

        global next_ticket_id

        if self.path != "/tickets":

            self.send_json_response(
                404,
                {"error": "Endpoint not found"}
            )
            return

        # Read request body
        content_length = int(
            self.headers.get("Content-Length", 0)
        )

        request_body = self.rfile.read(content_length)

        # Convert JSON request into Python data
        try:
            data = json.loads(
                request_body.decode("utf-8")
            )

        except json.JSONDecodeError:

            self.send_json_response(
                400,
                {"error": "Invalid JSON"}
            )
            return

        # Required fields from the Midterm specification
        required_fields = [
            "request_id",
            "client_id",
            "title",
            "client_lamport"
        ]

        # Check for missing fields
        missing_fields = [
            field
            for field in required_fields
            if field not in data
        ]

        if missing_fields:

            self.send_json_response(
                400,
                {
                    "error": "Missing required fields",
                    "missing_fields": missing_fields
                }
            )
            return

        # Extract request data
        request_id = data["request_id"]
        client_id = data["client_id"]
        title = data["title"]
        client_lamport = data["client_lamport"]

        # Basic validation
        if not isinstance(request_id, str) or not request_id.strip():

            self.send_json_response(
                400,
                {"error": "request_id must be a non-empty string"}
            )
            return

        if not isinstance(client_id, str) or not client_id.strip():

            self.send_json_response(
                400,
                {"error": "client_id must be a non-empty string"}
            )
            return

        if not isinstance(title, str) or not title.strip():

            self.send_json_response(
                400,
                {"error": "title must be a non-empty string"}
            )
            return

        if (
            not isinstance(client_lamport, int)
            or isinstance(client_lamport, bool)
            or client_lamport < 0
        ):

            self.send_json_response(
                400,
                {
                    "error": (
                        "client_lamport must be "
                        "a non-negative integer"
                    )
                }
            )
            return

        # Create ticket
        ticket = {
            "ticket_id": next_ticket_id,
            "request_id": request_id,
            "client_id": client_id,
            "title": title,
            "client_lamport": client_lamport,
            "status": "open"
        }

        tickets.append(ticket)

        next_ticket_id += 1

        # Return created ticket
        self.send_json_response(201, ticket)


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