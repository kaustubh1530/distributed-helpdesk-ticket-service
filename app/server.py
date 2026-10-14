from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request


# Logging

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/server.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# In-memory state

tickets = []
processed_requests = {}

next_ticket_id = 1
server_lamport = 0
server_sequence = 0


# Node configuration

NODE_NAME = "ticket-server"
ROLE = "leader"
PORT = 8000

# All cluster peers. The current node is excluded automatically
# by get_replication_targets(). This allows any promoted follower
# to replicate to the other two nodes.
FOLLOWERS = [
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:8002",
]

# Used for the reproducible delayed-response/retry test.
DELAY_RESPONSE_SECONDS = float(
    os.getenv("DELAY_RESPONSE_SECONDS", "0")
)

# Final project quorum requirement.
MAJORITY_REQUIRED = 2


def send_json_response(handler, status_code, data):
    """Send a JSON HTTP response."""
    response = json.dumps(data).encode("utf-8")

    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(response)))
    handler.end_headers()
    handler.wfile.write(response)


def get_replication_targets():
    """Return follower nodes other than the current node."""
    current_url = f"http://localhost:{PORT}"
    return [
        follower_url
        for follower_url in FOLLOWERS
        if follower_url != current_url
    ]


def replicate_ticket(ticket):
    """Send a ticket to the other nodes.

    Returns:
        replication_results:
            Detailed result for each target node.
        successful_replications:
            Number of target nodes that acknowledged successfully.
    """
    replication_results = []
    data = json.dumps(ticket).encode("utf-8")

    for follower_url in get_replication_targets():
        request = urllib.request.Request(
            f"{follower_url}/replicate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )

            replication_results.append(
                {
                    "node": follower_url,
                    "success": True,
                    "response": response_data,
                }
            )

        except urllib.error.URLError as error:
            replication_results.append(
                {
                    "node": follower_url,
                    "success": False,
                    "error": str(error.reason),
                }
            )

        except Exception as error:
            replication_results.append(
                {
                    "node": follower_url,
                    "success": False,
                    "error": str(error),
                }
            )

    successful_replications = sum(
        1
        for result in replication_results
        if result["success"]
    )

    return replication_results, successful_replications


def replicate_status_update(update):
    """Replicate a ticket status change to the other cluster nodes."""
    replication_results = []
    payload = json.dumps(update).encode("utf-8")

    for node_url in get_replication_targets():
        request = urllib.request.Request(
            f"{node_url}/replicate-status",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )

            replicated = response_data.get("replicated") is True
            replication_results.append(
                {
                    "node": node_url,
                    "success": replicated,
                    "response": response_data,
                }
            )

        except urllib.error.URLError as error:
            replication_results.append(
                {
                    "node": node_url,
                    "success": False,
                    "error": str(getattr(error, "reason", error)),
                }
            )
        except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
            replication_results.append(
                {
                    "node": node_url,
                    "success": False,
                    "error": str(error),
                }
            )
        except Exception as error:
            replication_results.append(
                {
                    "node": node_url,
                    "success": False,
                    "error": str(error),
                }
            )

    successful_replications = sum(
        1 for result in replication_results if result["success"]
    )
    return replication_results, successful_replications


def get_full_state():
    """Return the complete committed state for recovery."""
    return {
        "node_name": NODE_NAME,
        "role": ROLE,
        "tickets": tickets,
        "processed_requests": processed_requests,
        "next_ticket_id": next_ticket_id,
        "server_lamport": server_lamport,
        "server_sequence": server_sequence,
    }


def apply_full_state(state):
    """Replace local state with state received from the active leader."""
    global tickets
    global processed_requests
    global next_ticket_id
    global server_lamport
    global server_sequence

    tickets = list(state.get("tickets", []))
    processed_requests = dict(state.get("processed_requests", {}))
    next_ticket_id = int(state.get("next_ticket_id", 1))
    server_lamport = int(state.get("server_lamport", 0))
    server_sequence = int(state.get("server_sequence", 0))


class TicketRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        global server_lamport

        if self.path == "/health":
            response = {
                "node_name": NODE_NAME,
                "role": ROLE,
                "status": "healthy",
            }

            send_json_response(self, 200, response)
            return

        if self.path == "/tickets":
            response = {
                "node_name": NODE_NAME,
                "role": ROLE,
                "tickets": tickets,
                "server_lamport": server_lamport,
                "server_sequence": server_sequence,
            }

            send_json_response(self, 200, response)
            return

        if self.path == "/state":
            if ROLE != "leader":
                send_json_response(
                    self,
                    403,
                    {
                        "error": "Only the leader can provide recovery state"
                    },
                )
                return

            send_json_response(self, 200, get_full_state())
            return

        send_json_response(
            self,
            404,
            {"error": "Endpoint not found"},
        )

    def do_POST(self):
        global ROLE
        global next_ticket_id
        global server_lamport
        global server_sequence

        # Manual leader promotion.
        if self.path == "/promote":
            if ROLE != "follower":
                send_json_response(
                    self,
                    400,
                    {
                        "error": "Only a follower can be promoted"
                    },
                )
                return

            ROLE = "leader"

            logger.info(
                f"node_name={NODE_NAME} | "
                f"role=leader | "
                f"result=manual_promotion"
            )

            send_json_response(
                self,
                200,
                {
                    "node_name": NODE_NAME,
                    "role": ROLE,
                    "status": "promoted",
                    "tickets": len(tickets),
                    "server_lamport": server_lamport,
                    "server_sequence": server_sequence,
                },
            )
            return

        # Follower recovery endpoint.
        if self.path == "/recover":
            self.handle_recovery()
            return

        # Leader-side ticket status update endpoint.
        if self.path == "/tickets/status":
            self.handle_status_update()
            return

        # Follower status replication endpoint.
        if self.path == "/replicate-status":
            self.handle_status_replication()
            return

        # Follower ticket replication endpoint.
        if self.path == "/replicate":
            self.handle_replication()
            return

        # Client ticket endpoint.
        if self.path != "/tickets":
            send_json_response(
                self,
                404,
                {"error": "Endpoint not found"},
            )
            return

        # Followers do not accept direct client writes.
        if ROLE != "leader":
            send_json_response(
                self,
                403,
                {
                    "error": (
                        "Follower nodes do not accept client writes"
                    )
                },
            )
            return

        # Read request body.
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
                {"error": "Invalid JSON"},
            )
            return

        # Validate required fields.
        required_fields = [
            "request_id",
            "client_id",
            "title",
            "client_lamport",
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
                    "missing_fields": missing_fields,
                },
            )
            return

        request_id = data["request_id"]
        client_id = data["client_id"]
        title = data["title"]
        client_lamport = data["client_lamport"]

        # Validate request ID.
        if (
            not isinstance(request_id, str)
            or not request_id.strip()
        ):
            send_json_response(
                self,
                400,
                {
                    "error": (
                        "request_id must be a non-empty string"
                    )
                },
            )
            return

        # Validate client ID.
        if (
            not isinstance(client_id, str)
            or not client_id.strip()
        ):
            send_json_response(
                self,
                400,
                {
                    "error": (
                        "client_id must be a non-empty string"
                    )
                },
            )
            return

        # Validate title.
        if (
            not isinstance(title, str)
            or not title.strip()
        ):
            send_json_response(
                self,
                400,
                {
                    "error": "title must be a non-empty string"
                },
            )
            return

        # Validate Lamport clock.
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
                },
            )
            return

        # Idempotency check.
        if request_id in processed_requests:
            original_ticket = processed_requests[request_id]

            logger.info(
                f"request_id={request_id} | "
                f"client_id={client_id} | "
                f"logical_time="
                f"{original_ticket['server_lamport']} | "
                f"server_sequence="
                f"{original_ticket['server_sequence']} | "
                f"result=duplicate | "
                f"duplicate=true"
            )

            duplicate_response = dict(original_ticket)
            duplicate_response["duplicate"] = True
            duplicate_response["committed"] = True

            send_json_response(
                self,
                200,
                duplicate_response,
            )
            return

        # Lamport logical clock update.
        server_lamport = max(
            client_lamport,
            server_lamport,
        ) + 1

        # Server total ordering.
        server_sequence += 1

        # Create ticket candidate.
        ticket = {
            "ticket_id": next_ticket_id,
            "request_id": request_id,
            "client_id": client_id,
            "title": title,
            "client_lamport": client_lamport,
            "server_lamport": server_lamport,
            "server_sequence": server_sequence,
            "status": "open",
        }

        # Replicate before local commit.
        replication_results, successful_replications = (
            replicate_ticket(ticket)
        )

        # The leader counts as one acknowledgment.
        total_acknowledgments = (
            1 + successful_replications
        )

        majority_acknowledged = (
            total_acknowledgments >= MAJORITY_REQUIRED
        )

        # Majority failure: do not commit locally.
        if not majority_acknowledged:
            logger.info(
                f"request_id={request_id} | "
                f"client_id={client_id} | "
                f"logical_time={server_lamport} | "
                f"server_sequence={server_sequence} | "
                f"result=not_committed | "
                f"duplicate=false"
            )

            response = dict(ticket)
            response["replication"] = replication_results
            response["successful_replications"] = (
                successful_replications
            )
            response["majority_required"] = MAJORITY_REQUIRED
            response["majority_acknowledged"] = False
            response["committed"] = False

            send_json_response(
                self,
                503,
                response,
            )
            return

        # Majority succeeded: commit locally.
        tickets.append(ticket)
        next_ticket_id += 1

        processed_requests[request_id] = dict(ticket)

        logger.info(
            f"request_id={request_id} | "
            f"client_id={client_id} | "
            f"logical_time={server_lamport} | "
            f"server_sequence={server_sequence} | "
            f"result=created | "
            f"duplicate=false"
        )

        # Optional response delay for retry testing.
        if DELAY_RESPONSE_SECONDS > 0:
            logger.info(
                f"response_delay="
                f"{DELAY_RESPONSE_SECONDS} | "
                f"request_id={request_id}"
            )
            time.sleep(DELAY_RESPONSE_SECONDS)

        # Return successful result.
        response = dict(ticket)
        response["replication"] = replication_results
        response["successful_replications"] = (
            successful_replications
        )
        response["majority_required"] = MAJORITY_REQUIRED
        response["majority_acknowledged"] = True
        response["committed"] = True

        send_json_response(
            self,
            201,
            response,
        )

    def handle_recovery(self):
        """Recover this follower from the active leader."""
        global server_lamport

        if ROLE != "follower":
            send_json_response(
                self,
                403,
                {
                    "error": "Only follower nodes can recover"
                },
            )
            return

        content_length = int(
            self.headers.get("Content-Length", 0)
        )
        body = self.rfile.read(content_length)

        try:
            state = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            send_json_response(
                self,
                400,
                {
                    "error": "Invalid recovery state"
                },
            )
            return

        required_fields = [
            "tickets",
            "processed_requests",
            "next_ticket_id",
            "server_lamport",
            "server_sequence",
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in state
        ]

        if missing_fields:
            send_json_response(
                self,
                400,
                {
                    "error": "Missing recovery fields",
                    "missing_fields": missing_fields,
                },
            )
            return

        apply_full_state(state)

        logger.info(
            f"node_name={NODE_NAME} | "
            f"role={ROLE} | "
            f"result=recovered | "
            f"tickets={len(tickets)} | "
            f"server_lamport={server_lamport} | "
            f"server_sequence={server_sequence}"
        )

        send_json_response(
            self,
            200,
            {
                "node_name": NODE_NAME,
                "role": ROLE,
                "status": "recovered",
                "tickets": len(tickets),
                "server_lamport": server_lamport,
                "server_sequence": server_sequence,
            },
        )

    def handle_status_update(self):
        """Update a ticket's status on the leader and replicate the change."""
        global server_lamport
        global server_sequence

        if ROLE != "leader":
            send_json_response(
                self,
                403,
                {"error": "Only the leader can update ticket status"},
            )
            return

        content_length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            send_json_response(self, 400, {"error": "Invalid JSON"})
            return

        ticket_id = data.get("ticket_id")
        new_status = data.get("status")
        allowed_statuses = {"open", "in_progress", "closed"}

        if (
            isinstance(ticket_id, bool)
            or not isinstance(ticket_id, int)
            or ticket_id < 1
        ):
            send_json_response(
                self, 400, {"error": "ticket_id must be a positive integer"}
            )
            return

        if not isinstance(new_status, str) or new_status not in allowed_statuses:
            send_json_response(
                self,
                400,
                {"error": "Status must be open, in_progress, or closed"},
            )
            return

        ticket = next(
            (item for item in tickets if item.get("ticket_id") == ticket_id),
            None,
        )
        if ticket is None:
            send_json_response(self, 404, {"error": "Ticket not found"})
            return

        old_status = ticket.get("status", "open")
        if old_status == new_status:
            send_json_response(
                self,
                200,
                {
                    "node_name": NODE_NAME,
                    "ticket_id": ticket_id,
                    "previous_status": old_status,
                    "status": old_status,
                    "unchanged": True,
                    "committed": True,
                    "majority_acknowledged": True,
                },
            )
            return

        # Save the current values so a failed quorum attempt can be rolled back.
        old_lamport = server_lamport
        old_sequence = server_sequence
        old_status_lamport = ticket.get("status_lamport")
        old_status_sequence = ticket.get("status_sequence")

        server_lamport += 1
        server_sequence += 1
        ticket["status"] = new_status
        ticket["status_lamport"] = server_lamport
        ticket["status_sequence"] = server_sequence

        update = {
            "ticket_id": ticket_id,
            "status": new_status,
            "status_lamport": server_lamport,
            "status_sequence": server_sequence,
        }

        replication_results, successful_replications = (
            replicate_status_update(update)
        )
        majority_acknowledged = (
            1 + successful_replications >= MAJORITY_REQUIRED
        )

        if not majority_acknowledged:
            # Restore the local ticket and ordering counters if no follower
            # acknowledged the change. This is a teaching-project quorum
            # check, not a full consensus protocol.
            ticket["status"] = old_status
            server_lamport = old_lamport
            server_sequence = old_sequence

            if old_status_lamport is None:
                ticket.pop("status_lamport", None)
            else:
                ticket["status_lamport"] = old_status_lamport

            if old_status_sequence is None:
                ticket.pop("status_sequence", None)
            else:
                ticket["status_sequence"] = old_status_sequence

            processed_requests[ticket["request_id"]] = dict(ticket)

            send_json_response(
                self,
                503,
                {
                    "error": "Status update did not reach a majority",
                    "node_name": NODE_NAME,
                    "ticket_id": ticket_id,
                    "status": old_status,
                    "successful_replications": successful_replications,
                    "majority_required": MAJORITY_REQUIRED,
                    "majority_acknowledged": False,
                    "committed": False,
                    "replication_results": replication_results,
                },
            )
            return

        # Keep the idempotency record aligned with the updated ticket.
        processed_requests[ticket["request_id"]] = dict(ticket)

        logger.info(
            f"node_name={NODE_NAME} | operation=status_update | "
            f"ticket_id={ticket_id} | status={new_status} | "
            f"server_lamport={server_lamport} | "
            f"server_sequence={server_sequence} | committed=True"
        )

        send_json_response(
            self,
            200,
            {
                "node_name": NODE_NAME,
                "ticket_id": ticket_id,
                "previous_status": old_status,
                "status": new_status,
                "status_lamport": server_lamport,
                "status_sequence": server_sequence,
                "successful_replications": successful_replications,
                "majority_required": MAJORITY_REQUIRED,
                "majority_acknowledged": True,
                "committed": True,
                "replication_results": replication_results,
            },
        )

    def handle_status_replication(self):
        """Apply a leader's ticket status update on a follower."""
        global server_lamport
        global server_sequence

        if ROLE != "follower":
            send_json_response(
                self,
                403,
                {"error": "Only followers accept status replication"},
            )
            return

        content_length = int(self.headers.get("Content-Length", 0))
        try:
            update = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            send_json_response(self, 400, {"error": "Invalid JSON"})
            return

        ticket_id = update.get("ticket_id")
        new_status = update.get("status")
        status_lamport = update.get("status_lamport")
        status_sequence = update.get("status_sequence")

        if (
            isinstance(ticket_id, bool)
            or not isinstance(ticket_id, int)
            or ticket_id < 1
            or not isinstance(new_status, str)
            or new_status not in {"open", "in_progress", "closed"}
            or isinstance(status_lamport, bool)
            or not isinstance(status_lamport, int)
            or status_lamport < 0
            or isinstance(status_sequence, bool)
            or not isinstance(status_sequence, int)
            or status_sequence < 1
        ):
            send_json_response(self, 400, {"error": "Invalid status update"})
            return

        ticket = next(
            (item for item in tickets if item.get("ticket_id") == ticket_id),
            None,
        )
        if ticket is None:
            send_json_response(
                self,
                404,
                {
                    "error": (
                        "Ticket not found on follower; recover state first"
                    )
                },
            )
            return

        # Repeated delivery of the same status event is safe.
        if (
            ticket.get("status") == new_status
            and ticket.get("status_sequence") == status_sequence
        ):
            send_json_response(
                self,
                200,
                {
                    "node_name": NODE_NAME,
                    "replicated": True,
                    "duplicate": True,
                    "ticket_id": ticket_id,
                    "status": new_status,
                },
            )
            return

        # Do not overwrite a newer status event with an older one.
        current_status_sequence = ticket.get("status_sequence", 0)
        if status_sequence < current_status_sequence:
            send_json_response(
                self,
                200,
                {
                    "node_name": NODE_NAME,
                    "replicated": False,
                    "stale": True,
                    "ticket_id": ticket_id,
                    "current_status": ticket.get("status"),
                    "current_status_sequence": current_status_sequence,
                },
            )
            return

        ticket["status"] = new_status
        ticket["status_lamport"] = status_lamport
        ticket["status_sequence"] = status_sequence

        server_lamport = max(server_lamport, status_lamport)
        server_sequence = max(server_sequence, status_sequence)
        processed_requests[ticket["request_id"]] = dict(ticket)

        send_json_response(
            self,
            200,
            {
                "node_name": NODE_NAME,
                "replicated": True,
                "duplicate": False,
                "ticket_id": ticket_id,
                "status": new_status,
                "status_sequence": status_sequence,
            },
        )

    def handle_replication(self):
        global server_lamport
        global server_sequence
        global next_ticket_id

        # Only followers accept replication requests.
        if ROLE != "follower":
            send_json_response(
                self,
                403,
                {
                    "error": (
                        "Only follower nodes accept replication"
                    )
                },
            )
            return

        # Read replication body.
        content_length = int(
            self.headers.get("Content-Length", 0)
        )
        body = self.rfile.read(content_length)

        try:
            ticket = json.loads(
                body.decode("utf-8")
            )
        except json.JSONDecodeError:
            send_json_response(
                self,
                400,
                {"error": "Invalid JSON"},
            )
            return

        # Validate replicated ticket.
        required_fields = [
            "ticket_id",
            "request_id",
            "client_id",
            "title",
            "client_lamport",
            "server_lamport",
            "server_sequence",
            "status",
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
                    "error": "Missing replication fields",
                    "missing_fields": missing_fields,
                },
            )
            return

        request_id = ticket["request_id"]

        # Duplicate replication protection.
        if request_id in processed_requests:
            send_json_response(
                self,
                200,
                {
                    "node_name": NODE_NAME,
                    "replicated": False,
                    "duplicate": True,
                    "ticket_id": processed_requests[
                        request_id
                    ]["ticket_id"],
                },
            )
            return

        # Store replicated ticket.
        tickets.append(ticket)
        processed_requests[request_id] = dict(ticket)

        # Keep local counters synchronized.
        server_lamport = max(
            server_lamport,
            ticket["server_lamport"],
        )

        server_sequence = max(
            server_sequence,
            ticket["server_sequence"],
        )

        next_ticket_id = max(
            next_ticket_id,
            ticket["ticket_id"] + 1,
        )

        send_json_response(
            self,
            200,
            {
                "node_name": NODE_NAME,
                "replicated": True,
                "duplicate": False,
                "ticket_id": ticket["ticket_id"],
            },
        )


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
        print("Examples:")
        print(
            "python app/server.py "
            "ticket-server leader 8000"
        )
        print(
            "python app/server.py "
            "follower-B follower 8001"
        )
        print(
            "python app/server.py "
            "follower-C follower 8002"
        )
        return

    NODE_NAME = sys.argv[1]
    ROLE = sys.argv[2]
    PORT = int(sys.argv[3])

    server_address = (
        "localhost",
        PORT,
    )

    server = HTTPServer(
        server_address,
        TicketRequestHandler,
    )

    print()
    print("Distributed Help Desk Ticket Server")
    print("===================================")
    print(f"Node name : {NODE_NAME}")
    print(f"Role      : {ROLE}")
    print(f"Port      : {PORT}")
    print(f"URL       : http://localhost:{PORT}")
    print("Status    : healthy")
    print("===================================")
    print("Endpoints : /health /tickets /tickets/status /promote /replicate /replicate-status /state /recover")
    print("Press Ctrl+C to stop the server.")
    print()

    server.serve_forever()


if __name__ == "__main__":
    run_server()