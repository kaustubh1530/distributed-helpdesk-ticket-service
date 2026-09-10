import json
import sys
import urllib.request
import urllib.error
import uuid


SERVER_URL = "http://localhost:8000"

# Lamport logical clock for this client process
lamport_clock = 0


def increment_lamport_clock():
    global lamport_clock
    lamport_clock += 1
    return lamport_clock


def create_ticket(client_id, title):
    request_id = str(uuid.uuid4())

    # Increment Lamport clock before sending the request
    client_lamport = increment_lamport_clock()

    payload = {
        "request_id": request_id,
        "client_id": client_id,
        "title": title,
        "client_lamport": client_lamport
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        f"{SERVER_URL}/tickets",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    print("\nRequest sent:")
    print(json.dumps(payload, indent=2))

    try:
        with urllib.request.urlopen(request) as response:
            response_data = json.loads(response.read().decode("utf-8"))

        print("\nServer response:")
        print(json.dumps(response_data, indent=2))

    except urllib.error.HTTPError as error:
        print(f"\nHTTP error: {error.code}")
        print(error.read().decode("utf-8"))

    except urllib.error.URLError as error:
        print(f"\nConnection error: {error.reason}")


def main():
    global lamport_clock

    if len(sys.argv) != 2:
        print("Usage: python client/client.py <client_id>")
        return

    client_id = sys.argv[1]

    print(f"Connected as {client_id}")
    print("Enter a ticket title to create a ticket.")
    print("Type 'quit' to exit.")

    while True:
        title = input("\nTicket title: ").strip()

        if title.lower() == "quit":
            print(f"Final Lamport clock: {lamport_clock}")
            print("Client exiting.")
            break

        if not title:
            print("Ticket title cannot be empty.")
            continue

        create_ticket(client_id, title)


if __name__ == "__main__":
    main()