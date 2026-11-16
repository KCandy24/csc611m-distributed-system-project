import base64
import json
import socket
from argparse import ArgumentParser
from pathlib import Path

from src.protocol import receive_message, send_message
from src.shared import PROJECT_DIR
from util.read_config import read_master_config


def serve_image(image_path, port):
    task = {
        "type": "task",
        "id": 1,
        "filename": image_path.name,
        "image": base64.b64encode(image_path.read_bytes()).decode("ascii"),
    }

    with socket.create_server(("127.0.0.1", port)) as server:
        print(f"Listening on 127.0.0.1:{port}", flush=True)
        connection, _ = server.accept()
        with connection, connection.makefile("rwb") as stream:
            receive_message(stream, "request")
            send_message(stream, task)
            result = receive_message(stream, "result")
            if result.get("id") != task["id"]:
                raise ValueError("Result ID does not match the assigned image")

    print(json.dumps({
        "id": task["id"],
        "filename": task["filename"],
        "text": result["text"],
        "time_ms": result["time_ms"],
    }))


def main():
    parser = ArgumentParser(description="Send one PNG to an OCR worker.")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "master_config.txt")
    args = parser.parse_args()

    try:
        image_dir, port = read_master_config(args.config)
        image_path = min(image_dir.glob("*.png"), default=None)
        if image_path is None:
            raise ValueError(f"No PNG images found in {image_dir}")
        serve_image(image_path, port)
    except (EOFError, OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
