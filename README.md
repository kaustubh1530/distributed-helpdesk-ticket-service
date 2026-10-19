# Distributed Help Desk Ticket Service

## COMP421 — Distributed Systems II | Final Project

A distributed help desk ticket service built to demonstrate communication, logical clocks, request ordering, retry safety, leader-based replication, quorum acknowledgments, fault handling, and recovery.

The project extends the original Weeks 1–4 client-server implementation into a three-node prototype with a React frontend.

## 1. Project Overview

The service allows clients to create and retrieve help desk tickets. A leader coordinates ticket creation and replication to two follower nodes. The system includes bounded retries, request-ID idempotency, Lamport logical clocks, server-assigned sequence numbers, health checks, and recovery endpoints.

### Key Features

- HTTP/JSON client-server communication
- Three-node leader/follower architecture
- Leader-coordinated ticket replication
- Two-of-three acknowledgment policy for successful writes
- Lamport logical clocks and server-assigned sequence numbers
- Request-ID idempotency to prevent duplicate ticket creation
- Bounded client retries and timeout handling
- Health and replication-status endpoints
- Manual leader promotion and follower recovery
- React/Vite frontend
- Fault testing and structured server logs

**Important:** This is an educational replication prototype, not a complete Raft implementation. Leader promotion is manual, and recovery is not a fully automatic consensus or distributed recovery protocol.

## 2. Architecture

The system uses three server processes running on separate local ports.

| Node | Role | Address |
|---|---|---|
| `ticket-server` | Leader | `http://localhost:8000` |
| `follower-B` | Follower | `http://localhost:8001` |
| `follower-C` | Follower | `http://localhost:8002` |
| React frontend | Web UI | `http://localhost:5173` |

### Simplified architecture

```text
                 React Frontend
                localhost:5173
                       |
                       v
               Leader: port 8000
                 /           \
                v             v
       Follower-B           Follower-C
        port 8001            port 8002
```

The leader coordinates writes and replication. A write is considered successful only when the required two-of-three acknowledgment condition is satisfied.

If one follower is unavailable, the leader and remaining follower can form a two-node majority. If the leader cannot obtain the required acknowledgments, the write is rejected.

## 3. Technology Stack

- **Backend:** Python 3
- **Communication:** HTTP and JSON
- **Frontend:** React and Vite
- **Logical time:** Lamport clocks
- **Ordering:** Leader-assigned sequence numbers
- **Storage:** In-memory ticket state in the running processes
- **Testing:** HTTP requests and controlled node failures
- **Version control:** Git and GitHub

No external database is required by the current prototype.

## 4. Project Structure

```text
distributed-helpdesk-ticket-service/
├── app/
│   └── server.py
├── client/
│   └── client.py
├── frontend/
│   ├── package.json
│   └── src/
├── tests/
├── docs/
├── logs/
├── evidence/
├── README.md
├── requirements.txt
└── .gitignore
```

The exact contents of subdirectories may change as the project develops.

## 5. Requirements

Install the following tools:

- Python 3
- Node.js and npm
- Git
- Terminal or a compatible command-line shell

The commands below use macOS/Linux shell syntax.

## 6. Backend Setup

Clone the repository and enter the project directory:

```bash
git clone https://github.com/kaustubh1530/distributed-helpdesk-ticket-service.git
cd distributed-helpdesk-ticket-service
```

Create a virtual environment if needed:

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

Install the backend dependencies:

```bash
pip install -r requirements.txt
```

## 7. Start the Three Nodes

Open three separate Terminal windows or tabs. Run each command from the project root and keep all three processes running.

**Terminal 1 — Leader**

```bash
source venv/bin/activate
python app/server.py ticket-server leader 8000
```

**Terminal 2 — Follower B**

```bash
source venv/bin/activate
python app/server.py follower-B follower 8001
```

**Terminal 3 — Follower C**

```bash
source venv/bin/activate
python app/server.py follower-C follower 8002
```

### Check node health

From another Terminal window:

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8001/health
curl -i http://localhost:8002/health
```

The health response identifies the node, its role, and its status.

Additional endpoints for checking ticket state and replication include:

```bash
curl -i http://localhost:8000/tickets
curl -i http://localhost:8000/tickets/status
curl -i http://localhost:8000/replicate-status
curl -i http://localhost:8000/state
```

Repeat the appropriate requests against ports `8001` and `8002` when comparing node state.

## 8. Start the React Frontend

Open another Terminal window:

```bash
cd frontend
npm install
npm run dev
```

Open the local address printed by Vite, normally:

```text
http://localhost:5173
```

Keep the backend nodes running while using the frontend.

## 9. API Examples

### Health check — `GET /health`

```bash
curl http://localhost:8000/health
```

Checks the node's reported health and role.

### Create a ticket — `POST /tickets`

```bash
curl -i -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "demo-request-001",
    "client_id": "demo-student-01",
    "title": "Cannot connect to campus Wi-Fi",
    "client_lamport": 1
  }'
```

The request includes a unique request ID, client identifier, ticket title, and client logical timestamp.

Use a new request ID for a new ticket. To test idempotency, replay the same request with the same ID.

### List tickets — `GET /tickets`

```bash
curl -s http://localhost:8000/tickets | python -m json.tool
```

The response includes ticket state and ordering information, including the server Lamport clock and server sequence.

### Other endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Check node health |
| `POST /tickets` | Submit a ticket |
| `GET /tickets` | Retrieve ticket state |
| `GET /tickets/status` | Inspect ticket status information |
| `GET /replicate-status` | Inspect replication status |
| `GET /state` | Inspect node state |
| `POST /replicate` | Replication-related operation |
| `POST /promote` | Request leader promotion |
| `POST /recover` | Request recovery from the active leader |

The precise request formats and preconditions for administrative endpoints should be checked in `app/server.py` before using them.

## 10. Distributed Systems Concepts

### Lamport logical clocks

Lamport clocks represent logical ordering rather than synchronized wall-clock time. The server updates its logical clock when processing events, using the incoming client timestamp and its existing clock.

A simplified update rule is:

```text
server_lamport = max(client_lamport, server_lamport) + 1
```

### Server-assigned sequence numbers

The leader assigns sequence numbers to accepted ticket operations. These numbers provide an ordering for operations coordinated by the leader.

Sequence numbers and Lamport timestamps are different: the sequence tracks the assigned operation order, while the Lamport clock tracks logical event time.

### Bounded retries and idempotency

A client may time out even when a request has already been processed. Retrying with the same request ID allows the server to recognize a repeated operation and return the existing result instead of creating another ticket.

### Quorum acknowledgments

The prototype uses a two-of-three acknowledgment policy. The leader counts toward the required majority, so a write can proceed when the leader and one follower acknowledge it.

A successful response should not be interpreted as a guarantee of durable storage across arbitrary crashes. The implementation uses in-memory state and does not provide a complete consensus protocol.

## 11. Fault Testing

Run the following scenarios with the three nodes started. Record the HTTP responses, node states, and logs for your evidence folder.

### Test 1 — All nodes healthy

1. Start the leader and both followers.
2. Check the health of all three nodes.
3. Create a ticket through the leader.
4. Inspect the ticket state on each node.

**Expected observation:** A successful write should be reflected in the replicated state according to the implemented acknowledgment and replication behavior.

### Test 2 — One follower unavailable

1. Stop follower C using `Ctrl+C` in its Terminal.
2. Confirm the leader and follower B are running.
3. Submit a new ticket to the leader.
4. Inspect the response and available node state.

**Expected observation:** A write can succeed if the leader and the remaining follower satisfy the required majority.

Restart follower C after the experiment.

### Test 3 — No majority available

1. Stop both followers.
2. Submit a new ticket to the leader.
3. Inspect the HTTP response and ticket list.
4. Restart the followers.

**Expected observation:** The write should be rejected when the required majority cannot be obtained. Check the actual state and logs rather than assuming all counters remain unchanged.

### Test 4 — Duplicate request

Submit the same request twice with the same `request_id`.

**Expected observation:** A repeated committed request should not create a second ticket when the idempotency record is available.

### Test 5 — Recovery

1. Ensure the intended active leader has the committed ticket state.
2. Use the implemented recovery operation for the returning node.
3. Compare the recovered node's ticket list and state with the active leader.
4. Capture the results.

**Expected observation:** The recovery procedure should bring the node toward the active leader's state for the supported recovery scenario. Do not describe this as automatic catch-up unless it has been independently verified.

### Test 6 — Manual leader promotion

1. Stop or isolate the current leader.
2. Confirm that writes cannot safely proceed through the unavailable leader.
3. Designate an appropriate follower as the new leader using the supported promotion procedure.
4. Update the client or request destination as necessary.
5. Verify health and ticket state before testing new writes.

**Expected observation:** Leadership changes are manually controlled in this prototype. This is not an automatic Raft election.

## 12. Consistency, Availability, and Limitations

The project demonstrates the trade-offs involved in maintaining replicated state when nodes fail or cannot communicate.

- **Consistency:** Writes use leader coordination and a two-of-three acknowledgment condition. The prototype does not establish formal linearizability for every possible read and failure scenario.
- **Availability:** A write may continue with one follower unavailable if the leader and remaining follower acknowledge it. Without a majority, writes are rejected.
- **Stale reads:** A follower may temporarily expose state that has not caught up with the active leader. Read behavior must be evaluated against the actual endpoint implementation.
- **Recovery:** Recovery is an explicit operation, not a fully automatic synchronization protocol.
- **Persistence:** Ticket data is held in memory. A process restart can lose state unless the appropriate recovery or snapshot procedure is used.
- **Failover:** Leader promotion is manual.
- **Consensus:** The project does not implement the full Raft election, log replication, and safety protocol.

These limitations are part of the project's distributed-systems analysis and should be considered when interpreting fault-test results.

## 13. Protocol and Design Comparisons

The final report discusses the prototype in relation to:

- **Raft:** Leader-based replication and quorum ideas, while distinguishing the prototype from full consensus.
- **Two-Phase Commit (2PC):** Coordinating distributed transactions and the availability costs associated with waiting for participants.
- **CAP theorem:** The trade-off between consistency and availability during network partitions.
- **CRDTs:** An alternative approach for some replicated data types when concurrent updates and eventual convergence are acceptable.
- **Spanner:** A comparison point for globally distributed consistency and time-related design, beyond the guarantees provided by this local prototype.

These comparisons are analytical; they do not imply that the project implements these systems or protocols.

## 14. Evidence and Documentation

Use the `evidence/` directory to organize verified screenshots, command outputs, and fault-test traces.

Recommended evidence includes:

- All-node health checks
- Ticket creation and ticket-list output
- Duplicate-request behavior
- One-follower-down test
- No-majority rejection
- Recovery and node-state comparison
- Manual promotion test
- Frontend dashboard

Keep evidence free of private information, credentials, and secrets. Include only test results that were actually observed.

The final submission may also include the architecture diagram, interface specification, requirement-to-test traceability matrix, final report, presentation slides, and demo recording required by the course.

## 15. Running the Original Client

The original Python client can still be used for client-server demonstrations:

```bash
source venv/bin/activate
python client/client.py client-A
```

Run another client in a separate terminal if you want to demonstrate concurrent client requests and server-assigned ordering.

## 16. Academic Integrity and AI Assistance

AI tools were used as development assistance for explanation, debugging support, documentation, and code-development guidance. Implementation behavior and reported test results should be supported by the student's own execution and evidence.

Follow the University's requirements for disclosing and citing AI assistance. Be prepared to explain the code, design decisions, limitations, and test results.

## 17. Repository

GitHub: https://github.com/kaustubh1530/distributed-helpdesk-ticket-service
