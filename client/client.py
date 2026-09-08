import json
import urllib.request
import urllib.error


SERVER_URL = "http://localhost:8000"


def create_ticket(client_id, title):
    """Send a request to create a new help desk ticket."""

    data = {
        "client_id": client_id,
        "title": title
    }

    request_data = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        f"{SERVER_URL}/tickets",
        data=request_data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request) as response:
            response_data = response.read().decode("utf-8")

            print(f"\nClient: {client_id}")
            print("Server response:")
            print(json.dumps(json.loads(response_data), indent=2))

    except urllib.error.HTTPError as error:
        print(f"HTTP Error: {error.code}")
        print(error.read().decode("utf-8"))

    except urllib.error.URLError as error:
        print(f"Connection Error: {error.reason}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("python client/client.py <client_id> <ticket_title>")
        sys.exit(1)

    client_id = sys.argv[1]
    title = " ".join(sys.argv[2:])

    create_ticket(client_id, title)