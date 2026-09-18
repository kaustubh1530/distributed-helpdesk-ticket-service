# Guided Distributed Help Desk Ticket Service

## COMP421 Distributed Systems II — Midterm Project

A small client-server ticket service developed to demonstrate core distributed-systems concepts from Weeks 1–4:

- HTTP/JSON communication
- Client and server Lamport logical clocks
- Server-assigned total ordering
- Bounded timeout and retry
- Request-ID idempotency
- In-memory ticket storage
- Structured server logging
- Two-client ordering

The Midterm architecture uses **one ticket server and two clients**. The later three-node replication work is treated as preparation for the Weeks 5–8 Final extension.

---

## 1. Project Structure

```text
distributed-helpdesk-ticket-service/
├── app/
│   └── server.py
├── client/
│   └── client.py
├── tests/
├── docs/
├── logs/
├── evidence/
├── README.md
├── requirements.txt
└── .gitignore
```

---

## 2. Requirements

- Python 3
- macOS, Linux, or Windows
- Terminal
- No external database is required for the Midterm

The project uses Python's standard-library HTTP/JSON functionality.

---

## 3. Setup

From the project directory:

```bash
cd ~/Desktop/distributed-helpdesk-ticket-service
```

Create the virtual environment if it does not already exist:

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

On Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

---

## 4. Start the Midterm Server

Open Terminal 1 and run:

```bash
python app/server.py ticket-server leader 8000
```

The server listens on:

```text
http://localhost:8000
```

Keep this terminal running during the tests.

> Note: The current code also contains the Final-stage replication hooks. For the Midterm tests, the required behavior is evaluated through the single leader/server on port 8000. If follower processes are not running, replication connection errors may appear in the response; these are not part of the Midterm success criteria.

---

## 5. Verify Server Health

From another terminal:

```bash
curl http://localhost:8000/health
```

Expected structure:

```json
{
  "node_name": "ticket-server",
  "role": "leader",
  "status": "healthy"
}
```

This verifies that the server is running.

---

## 6. Run a Client

Open Terminal 2:

```bash
source venv/bin/activate
python client/client.py client-A
```

Enter a ticket title when prompted.

For a second client, open Terminal 3:

```bash
source venv/bin/activate
python client/client.py client-B
```

Each client maintains its own Lamport clock and generates a request ID for each ticket operation.

---

# 7. API

## GET /health

Checks server status.

```bash
curl http://localhost:8000/health
```

## POST /tickets

Creates a ticket.

Example:

```bash
curl -X POST http://localhost:8000/tickets -H "Content-Type: application/json" -d '{"request_id":"example-001","client_id":"client-A","title":"Cannot connect to campus WiFi","client_lamport":1}'
```

Required fields:

```text
request_id
client_id
title
client_lamport
```

## GET /tickets

Returns current ticket state and ordering information.

```bash
curl http://localhost:8000/tickets
```

The response includes:

```text
tickets
server_lamport
server_sequence
```

---

# 8. Midterm Test Procedures

The Midterm requires four test scenarios.

## Test 1 — Normal Request

Start a fresh server and submit:

```bash
curl -X POST http://localhost:8000/tickets -H "Content-Type: application/json" -d '{"request_id":"midterm-normal-002","client_id":"client-A","title":"Normal request test","client_lamport":1}'
```

Then check state:

```bash
curl http://localhost:8000/tickets
```

Expected result:

- One ticket is created.
- `server_sequence` becomes 1.
- `server_lamport` becomes 2 for this clean test.
- The ticket status is `open`.

Evidence:

```text
evidence/normal_request.png
evidence/normal_request_state.png
```

---

## Test 2 — Delayed Response and Bounded Retry

This is a controlled experiment used to demonstrate timeout uncertainty.

The experiment temporarily configured the server to delay its response for 5 seconds after committing the ticket while the client timeout was 3 seconds.

The client therefore:

1. Sends Attempt 1.
2. Times out after 3 seconds.
3. Retries.
4. Reuses the exact same request ID.
5. Receives the original ticket from the server's idempotency cache.

Observed request ID:

```text
e9355191-3309-43f3-917e-56e47d39ce5b
```

The final state contained one ticket with:

```text
ticket_id = 1
server_lamport = 2
server_sequence = 1
duplicate = true
```

The temporary delay was removed after the controlled experiment and is not part of normal server operation.

Evidence:

```text
evidence/delayed_retry_client.png
evidence/delayed_retry_state.png
evidence/delayed_retry_log.png
```

---

## Test 3 — Duplicate Request / Idempotency

Submit the same request ID twice.

First request:

```bash
curl -X POST http://localhost:8000/tickets -H "Content-Type: application/json" -d '{"request_id":"midterm-duplicate-001","client_id":"client-A","title":"Duplicate request test","client_lamport":1}'
```

Send the exact same request again:

```bash
curl -X POST http://localhost:8000/tickets -H "Content-Type: application/json" -d '{"request_id":"midterm-duplicate-001","client_id":"client-A","title":"Duplicate request test","client_lamport":1}'
```

Then verify state:

```bash
curl http://localhost:8000/tickets
```

Expected result:

- The first request creates the ticket.
- The second request returns the original ticket.
- The second response contains `duplicate: true`.
- No second ticket is created.
- The server sequence does not increase for the duplicate.

Evidence:

```text
evidence/duplicate_request.png
evidence/duplicate_request_state.png
evidence/duplicate_request_log.png
```

---

## Test 4 — Two-Client Ordering

Start a fresh server.

Run Client A:

```bash
python client/client.py client-A
```

Run Client B in another terminal:

```bash
python client/client.py client-B
```

Submit the requests close together.

The clean ordering experiment produced:

```text
Client A
client_lamport = 1
server_lamport = 2
server_sequence = 1

Client B
client_lamport = 1
server_lamport = 3
server_sequence = 2
```

The server sequence provides a simple total order for accepted requests at the server.

Check the final state:

```bash
curl http://localhost:8000/tickets
```

Evidence:

```text
evidence/ordering_client_A.png
evidence/ordering_client_B.png
evidence/ordering_server_tickets.png
```

---

# 9. Lamport Clock Rule

The server uses:

```text
max(client_lamport, server_lamport) + 1
```

For example:

```text
Client A sends: client_lamport = 1
Server updates: server_lamport = 2

Client B sends: client_lamport = 1
Server updates: server_lamport = 3
```

Lamport timestamps represent **logical time/order**, not synchronized wall-clock time.

---

# 10. Retry and Idempotency

The client uses:

- 3-second request timeout
- Maximum of 2 retries
- Maximum of 3 total attempts
- One request ID reused across all attempts

The server stores completed request results by `request_id`.

Therefore, if a retry arrives after the original request was already committed, the server can return the original result instead of creating another ticket.

---

# 11. Structured Logging

Server logs are stored in:

```text
logs/server.log
```

The log records:

```text
request_id
client_id
logical_time
server_sequence
result
duplicate status
```

Example:

```text
request_id=midterm-duplicate-001 | client_id=client-A |
logical_time=2 | server_sequence=1 |
result=created | duplicate=false
```

A repeated request produces a duplicate log entry rather than another ticket creation.

---

# 12. Midterm Limitations

The Midterm intentionally uses a simple architecture:

- One server
- Two clients
- In-memory state
- No persistent database
- No automatic failover
- No quorum/consensus protocol

Restarting the server clears the in-memory ticket state.

---

# 13. Weeks 5–8 Final Extension

The planned Final extension expands the system to a three-node leader/follower architecture:

```text
Leader:   localhost:8000
Follower: localhost:8001
Follower: localhost:8002
```

Planned Final work includes:

- Leader-based replication
- Two-of-three acknowledgment / quorum
- Follower failure handling
- Manual leader failover
- Recovery
- Explicit consistency analysis
- Comparison with Raft, 2PC, CAP, CRDTs, and Spanner concepts

The replication prototype is treated as Final preparation and is not used to redefine the Midterm's single-server requirements.

---

# 14. Evidence

All Midterm evidence is stored in:

```text
evidence/
```

The evidence covers:

1. Normal request
2. Delayed response and retry
3. Duplicate request / idempotency
4. Two-client ordering

See the project report for the detailed test results and interpretation.

---

# 15. Academic Integrity / AI Assistance

AI tools were used as development assistance for explanation, debugging support, documentation, and code-development guidance. The submitted implementation, test behavior, screenshots, and results were executed and verified by the student.

Students submitting this project should follow the University's requirements for disclosure and citation of AI assistance.
