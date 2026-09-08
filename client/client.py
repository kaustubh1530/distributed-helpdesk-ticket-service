import json
import sys
import urllib.request
import urllib.error
import uuid


SERVER_URL = "http://localhost:8000"


def create_ticket(
    client_id,
    title,
    client_lamport=1
):
    """Send a ticket creation request to the server."""

    request_id = str(uuid.uuid4())

    data = {
        "request_id": request_id,
        "client_id": client_id,
        "title": title,
        "client_lamport": client_lamport
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

            response_data = response.read().decode(
                "utf-8"
            )

            print("\nRequest sent:")
            print(
                json.dumps(
                    data,
                    indent=2
                )
            )

            print("\nServer response:")
            print(
                json.dumps(
                    json.loads(response_data),
                    indent=2
                )
            )

    except urllib.error.HTTPError as error:

        print(f"\nHTTP Error: {error.code}")
        print(error.read().decode("utf-8"))

    except urllib.error.URLError as error:

        print(
            f"\nConnection Error: {error.reason}"
        )


if __name__ == "__main__":

    if len(sys.argv) < 3:

        print(
            "Usage:\n"
            "python client/client.py "
            "<client_id> <ticket_title>"
        )

        sys.exit(1)

    client_id = sys.argv[1]

    title = " ".join(sys.argv[2:])

    create_ticket(
        client_id,
        title
    )
    