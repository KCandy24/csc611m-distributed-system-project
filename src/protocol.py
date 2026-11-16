import json


def send_message(stream, message):
    # End each JSON message with a newline so the receiver can read it in full.
    stream.write(json.dumps(message).encode("utf-8") + b"\n")
    stream.flush()


def receive_message(stream, expected_type):
    line = stream.readline()
    if not line:
        raise EOFError(f"Connection closed while waiting for {expected_type}")

    message = json.loads(line)
    if not isinstance(message, dict) or message.get("type") != expected_type:
        raise ValueError(f"Expected a {expected_type} message")
    return message
