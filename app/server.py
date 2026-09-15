from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys
import urllib.request
import urllib.error


# In-memory ticket storage

tickets = []

# Next ticket ID
next_ticket_id = 1

# Server Lamport logical clock
server_lamport = 0

# Server-assigned ordering sequence
server_sequence = 0


# Node configuration

NODE_NAME = "ticket-server"
ROLE = "leader"
PORT = 8000

# Followers used by the leader
FOLLOWERS = [
    "http://localhost:8001",
    "http://localhost:8002"
]


# Request idempotency tracking

processed_requests = {}


# JSON response helper

def send_json_response(handler, status_code, data):
    response = json.dumps(data).encode("utf-8")

    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(response)))
    handler.end_headers()

    handler.wfile.write(response)


# Replication helper

def replicate_ticket(ticket):
    """
    Leader sends a ticket to both followers.

    This phase demonstrates basic synchronous-style
    replication, but quorum acknowledgment is NOT
    implemented yet. That comes in Phase 6.
    """

    replication_results = []

    data = json.dumps(ticket).encode("utf-8")

    for follower_url in FOLLOWERS:

        request = urllib.request.Request(
            f"{follower_url}/replicate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=2
            ) as response:

                response_data = json.loads(
                    response.read().decode("utf-8")
                )

            replication_results.append({
                "node": follower_url,
                "success": True,
                "response": response_data
            })

        except urllib.error.URLError as error:

            replication_results.append({
                "node": follower_url,
                "success": False,
                "error": str(error.reason)
            })

        except Exception as error:

            replication_results.append({
                "node": follower_url,
                "success": False,
                "error": str(error)
            })

    return replication_results


# Request handler

class TicketRequestHandler(BaseHTTPRequestHandler):

    # GET endpoints

    def do_GET(self):

        if self.path == "/health":

            response = {
                "node_name": NODE_NAME,
                "role": ROLE,
                "status": "healthy"
            }

            send_json_response(
                self,
                200,
                response
            )

        elif self.path == "/tickets":

            response = {
                "node_name": NODE_NAME,
                "role": ROLE,
                "tickets": tickets,
                "server_lamport": server_lamport,
                "server_sequence": server_sequence
            }

            send_json_response(
                self,
                200,
                response
            )

        else:

            send_json_response(
                self,
                404,
                {
                    "error": "Endpoint not found"
                }
            )

    # POST endpoints

    def do_POST(self):

        global next_ticket_id
        global server_lamport
        global server_sequence

        # Replication endpoint

        if self.path == "/replicate":

            self.handle_replication()

            return
        # Client ticket endpoint

        if self.path != "/tickets":

            send_json_response(
                self,
                404,
                {
                    "error": "Endpoint not found"
                }
            )

            return

        # Followers do not accept client writes

        if ROLE != "leader":

            send_json_response(
                self,
                403,
                {
                    "error":
                    "Follower nodes do not accept client writes"
                }
            )

            return

        # Read request body

        content_length = int(
            self.headers.get(
                "Content-Length",
                0
            )
        )

        body = self.rfile.read(
            content_length
        )

        # Parse JSON

        try:

            data = json.loads(
                body.decode("utf-8")
            )

        except json.JSONDecodeError:

            send_json_response(
                self,
                400,
                {
                    "error": "Invalid JSON"
                }
            )

            return

        # Required fields

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
                    "error":
                    "Missing required fields",
                    "missing_fields":
                    missing_fields
                }
            )

            return

        request_id = data["request_id"]
        client_id = data["client_id"]
        title = data["title"]
        client_lamport = data["client_lamport"]

        # Validate request ID

        if (
            not isinstance(request_id, str)
            or not request_id.strip()
        ):

            send_json_response(
                self,
                400,
                {
                    "error":
                    "request_id must be a non-empty string"
                }
            )

            return

        # Validate client ID

        if (
            not isinstance(client_id, str)
            or not client_id.strip()
        ):

            send_json_response(
                self,
                400,
                {
                    "error":
                    "client_id must be a non-empty string"
                }
            )

            return

        # Validate title

        if (
            not isinstance(title, str)
            or not title.strip()
        ):

            send_json_response(
                self,
                400,
                {
                    "error":
                    "title must be a non-empty string"
                }
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
                    "error":
                    "client_lamport must be a "
                    "non-negative integer"
                }
            )

            return

        # Idempotency check

        if request_id in processed_requests:

            original_ticket = processed_requests[
                request_id
            ]

            duplicate_response = dict(
                original_ticket
            )

            duplicate_response["duplicate"] = True

            send_json_response(
                self,
                200,
                duplicate_response
            )

            return

        # Lamport logical clock update

        server_lamport = max(
            client_lamport,
            server_lamport
        ) + 1

        # Server total ordering

        server_sequence += 1

        # Create ticket

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

        # Store request result for idempotency

        processed_requests[
            request_id
        ] = dict(ticket)

        # Replicate to followers

        replication_results = replicate_ticket(
            ticket
        )

        # Return result

        response = dict(ticket)

        response["replication"] = replication_results

        send_json_response(
            self,
            201,
            response
        )

    # Replication handler

    def handle_replication(self):

        global server_lamport
        global server_sequence
        global next_ticket_id

        # Only followers should receive replication
        if ROLE != "follower":

            send_json_response(
                self,
                403,
                {
                    "error":
                    "Only follower nodes accept replication"
                }
            )

            return

        content_length = int(
            self.headers.get(
                "Content-Length",
                0
            )
        )

        body = self.rfile.read(
            content_length
        )

        try:

            ticket = json.loads(
                body.decode("utf-8")
            )

        except json.JSONDecodeError:

            send_json_response(
                self,
                400,
                {
                    "error": "Invalid JSON"
                }
            )

            return

        # Validate replicated ticket

        required_fields = [
            "ticket_id",
            "request_id",
            "client_id",
            "title",
            "client_lamport",
            "server_lamport",
            "server_sequence",
            "status"
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in ticket
        ]

        if missing_fields:

            send_json_response(
                self,
                400,
                {
                    "error":
                    "Missing replication fields",
                    "missing_fields":
                    missing_fields
                }
            )

            return

        request_id = ticket["request_id"]

        # Duplicate replication protection

        if request_id in processed_requests:

            send_json_response(
                self,
                200,
                {
                    "node_name": NODE_NAME,
                    "replicated": False,
                    "duplicate": True,
                    "ticket_id":
                    processed_requests[
                        request_id
                    ]["ticket_id"]
                }
            )

            return

        # Store ticket

        tickets.append(ticket)

        processed_requests[
            request_id
        ] = dict(ticket)

        # Keep local counters synchronized
        server_lamport = max(
            server_lamport,
            ticket["server_lamport"]
        )

        server_sequence = max(
            server_sequence,
            ticket["server_sequence"]
        )

        next_ticket_id = max(
            next_ticket_id,
            ticket["ticket_id"] + 1
        )

        send_json_response(
            self,
            200,
            {
                "node_name": NODE_NAME,
                "replicated": True,
                "duplicate": False,
                "ticket_id":
                ticket["ticket_id"]
            }
        )


# Run server

def run_server():

    global NODE_NAME
    global ROLE
    global PORT

    if len(sys.argv) != 4:

        print(
            "Usage: python app/server.py "
            "<node_name> <role> <port>"
        )

        print()

        print(
            "Examples:"
        )

        print(
            "python app/server.py leader leader 8000"
        )

        print(
            "python app/server.py follower-B follower 8001"
        )

        print(
            "python app/server.py follower-C follower 8002"
        )

        return

    NODE_NAME = sys.argv[1]

    ROLE = sys.argv[2]

    PORT = int(
        sys.argv[3]
    )

    server_address = (
        "localhost",
        PORT
    )

    server = HTTPServer(
        server_address,
        TicketRequestHandler
    )

    print()
    print("======================================")
    print("Distributed Help Desk Ticket Server")
    print("======================================")
    print(f"Node name : {NODE_NAME}")
    print(f"Role      : {ROLE}")
    print(f"Port      : {PORT}")
    print(
        f"URL       : http://localhost:{PORT}"
    )
    print("Status    : healthy")
    print("======================================")
    print("Press Ctrl+C to stop the server.")
    print()

    server.serve_forever()


if __name__ == "__main__":
    run_server()