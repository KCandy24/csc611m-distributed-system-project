import base64
import socket
from argparse import ArgumentParser
from io import BytesIO
from pathlib import Path

from PIL import Image

from src.protocol import receive_message, send_message
from src.recognition import recognize_image
from src.shared import PROJECT_DIR
from util.read_config import read_worker_config


def process_image(master_host, master_port):
    with socket.create_connection((master_host, master_port)) as connection:
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


def main():
    parser = ArgumentParser(description="Request one PNG from the OCR master.")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "worker_config.txt")
    args = parser.parse_args()

    try:
        master_host, master_port, n_workers = read_worker_config(args.config)
        if n_workers != 1:
            raise ValueError("The single-image run requires n_workers=1")
        process_image(master_host, master_port)
    except (EOFError, OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
