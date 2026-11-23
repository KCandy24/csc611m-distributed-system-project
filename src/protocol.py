import json


def send_message(stream, message):
    # End each JSON message with a newline so the receiver can read it in full.
    stream.write(json.dumps(message).encode("utf-8") + b"\n")
    stream.flush()


def receive_message(stream, *expected_types):
    expected = " or ".join(expected_types)
    line = stream.readline()
    if not line:
        raise EOFError(f"Connection closed while waiting for {expected}")

    message = json.loads(line)
    if not isinstance(message, dict) or message.get("type") not in expected_types:
        raise ValueError(f"Expected a {expected} message")
    return message
