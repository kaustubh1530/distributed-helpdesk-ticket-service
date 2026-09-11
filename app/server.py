from http.server import BaseHTTPRequestHandler, HTTPServer

import json
import time


# In-memory ticket storage
tickets = []

# Next ticket ID
next_ticket_id = 1

# Server Lamport logical clock
server_lamport = 0

# Server-assigned ordering sequence
server_sequence = 0

# Phase 4 controlled timeout experiment
# True = delay successful responses by 5 seconds
# False = normal operation
DELAY_RESPONSE = True
DELAY_SECONDS = 5


def send_json_response(handler, status_code, data):
    response = json.dumps(data).encode("utf-8")

    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(response)))
    handler.end_headers()
    handler.wfile.write(response)


class TicketRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        global server_lamport
        global server_sequence

        if self.path == "/health":
            response = {
                "node_name": "ticket-server",
                "role": "single-server",
                "status": "healthy"
            }

            send_json_response(self, 200, response)

        elif self.path == "/tickets":
            response = {
                "tickets": tickets,
                "server_lamport": server_lamport,
                "server_sequence": server_sequence
            }

            send_json_response(self, 200, response)

        else:
            send_json_response(
                self,
                404,
                {"error": "Endpoint not found"}
            )

    def do_POST(self):
        global next_ticket_id
        global server_lamport
        global server_sequence

        if self.path != "/tickets":
            send_json_response(
                self,
                404,
                {"error": "Endpoint not found"}
            )
            return

        content_length = int(
            self.headers.get("Content-Length", 0)
        )

        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8"))

        except json.JSONDecodeError:
            send_json_response(
                self,
                400,
                {"error": "Invalid JSON"}
            )
            return

        required_fields = [
            "request_id",
            "client_id",
            "title",
            "client_lamport"
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in data
        ]

        if missing_fields:
            send_json_response(
                self,
                400,
                {
                    "error": "Missing required fields",
                    "missing_fields": missing_fields
                }
            )
            return

        request_id = data["request_id"]
        client_id = data["client_id"]
        title = data["title"]
        client_lamport = data["client_lamport"]

        # Validate string fields
        if (
            not isinstance(request_id, str)
            or not request_id.strip()
        ):
            send_json_response(
                self,
                400,
                {"error": "request_id must be a non-empty string"}
            )
            return

        if (
            not isinstance(client_id, str)
            or not client_id.strip()
        ):
            send_json_response(
                self,
                400,
                {"error": "client_id must be a non-empty string"}
            )
            return

        if (
            not isinstance(title, str)
            or not title.strip()
        ):
            send_json_response(
                self,
                400,
                {"error": "title must be a non-empty string"}
            )
            return

        # Validate Lamport clock
        if (
            isinstance(client_lamport, bool)
            or not isinstance(client_lamport, int)
            or client_lamport < 0
        ):
            send_json_response(
                self,
                400,
                {
                    "error": (
                        "client_lamport must be a "
                        "non-negative integer"
                    )
                }
            )
            return

        # -------------------------------------------------
        # DUPLICATE / IDEMPOTENCY CHECK
        # -------------------------------------------------
        for existing_ticket in tickets:
            if existing_ticket["request_id"] == request_id:

                duplicate_response = existing_ticket.copy()

                duplicate_response["duplicate"] = True

                print(
                    f"[DUPLICATE] request_id={request_id} "
                    f"ticket_id={existing_ticket['ticket_id']}"
                )

                send_json_response(
                    self,
                    200,
                    duplicate_response
                )

                return

        # -------------------------------------------------
        # Lamport logical clock update
        # -------------------------------------------------
        server_lamport = max(
            client_lamport,
            server_lamport
        ) + 1

        # Assign server ordering sequence
        server_sequence += 1

        # -------------------------------------------------
        # Create ticket
        # -------------------------------------------------
        ticket = {
            "ticket_id": next_ticket_id,
            "request_id": request_id,
            "client_id": client_id,
            "title": title,
            "client_lamport": client_lamport,
            "server_lamport": server_lamport,
            "server_sequence": server_sequence,
            "status": "open"
        }

        tickets.append(ticket)

        next_ticket_id += 1

        print(
            f"[CREATE] request_id={request_id} "
            f"ticket_id={ticket['ticket_id']} "
            f"server_sequence={server_sequence}"
        )

        # -------------------------------------------------
        # Controlled delay for Phase 4 timeout test
        # -------------------------------------------------
        if DELAY_RESPONSE:
            print(
                f"[DELAY] Waiting {DELAY_SECONDS} seconds "
                f"before sending response..."
            )

            time.sleep(DELAY_SECONDS)

        # Send original response
        send_json_response(
            self,
            201,
            ticket
        )


def run_server():

    server_address = ("localhost", 8000)

    server = HTTPServer(
        server_address,
        TicketRequestHandler
    )

    print(
        "Help Desk Ticket Server running on "
        "http://localhost:8000"
    )

    print(
        f"Response delay enabled: "
        f"{DELAY_RESPONSE}"
    )

    if DELAY_RESPONSE:
        print(
            f"Response delay: "
            f"{DELAY_SECONDS} seconds"
        )

    print("Press Ctrl+C to stop the server.")

    server.serve_forever()


if __name__ == "__main__":
    run_server()