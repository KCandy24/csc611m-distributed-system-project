import base64
import socket
from io import BytesIO

from PIL import Image

from src.protocol import receive_message, send_message
from src.recognition import recognize_image


class Worker_Node:
    def __init__(self, master_host, master_port, n_workers):
        self.master_host = master_host
        self.master_port = master_port
        self.n_workers = n_workers

    def run(self):
        if self.n_workers != 1:
            raise ValueError("The single-image run requires n_workers=1")

        with socket.create_connection((self.master_host, self.master_port)) as connection:
            with connection.makefile("rwb") as stream:
                send_message(stream, {"type": "request"})
                task = receive_message(stream, "task")
                image_bytes = base64.b64decode(task["image"], validate=True)
                with Image.open(BytesIO(image_bytes)) as image:
                    text, time_ms = recognize_image(image)

                send_message(stream, {
                    "type": "result",
                    "id": task["id"],
                    "text": text,
                    "time_ms": round(time_ms, 4),
                })

        print(f"Processed {task['filename']}")
