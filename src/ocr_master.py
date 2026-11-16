import base64
import json
import socket

from src.protocol import receive_message, send_message


class OCR_Master:
    def __init__(self, image_dir, port):
        self.image_dir = image_dir
        self.port = port

    def run(self):
        image_path = min(self.image_dir.glob("*.png"), default=None)
        if image_path is None:
            raise ValueError(f"No PNG images found in {self.image_dir}")

        task = {
            "type": "task",
            "id": 1,
            "filename": image_path.name,
            "image": base64.b64encode(image_path.read_bytes()).decode("ascii"),
        }

        with socket.create_server(("127.0.0.1", self.port)) as server:
            print(f"Listening on 127.0.0.1:{self.port}", flush=True)
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
