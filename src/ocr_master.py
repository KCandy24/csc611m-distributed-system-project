import base64
import csv
import socket
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.protocol import receive_message, send_message


class OCR_Master:
    def __init__(self, image_dir, port, output_path):
        self.image_dir = image_dir
        self.port = port
        self.output_path = output_path

    def run(self):
        image_paths = sorted(path for path in self.image_dir.glob("*.png") if path.is_file())
        if not image_paths:
            raise ValueError(f"No PNG images found in {self.image_dir}")

        with socket.create_server(("127.0.0.1", self.port)) as server:
            print(f"Listening on 127.0.0.1:{self.port}", flush=True)
            connection, _ = server.accept()
            with connection, connection.makefile("rwb") as stream:
                self._process_batch(stream, image_paths)
                send_message(stream, {"type": "no_tasks"})

        print(f"Saved {len(image_paths)} OCR results to {self.output_path}")

    def _process_batch(self, stream, image_paths):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        # Keep the previous CSV until the full batch has completed.
        output_file = NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=self.output_path.parent,
            delete=False,
        )
        temp_path = Path(output_file.name)
        try:
            with output_file:
                writer = csv.writer(output_file)
                writer.writerow(["id", "filename", "text", "time_ms"])

                for image_id, image_path in enumerate(image_paths, start=1):
                    receive_message(stream, "request")
                    send_message(stream, {
                        "type": "task",
                        "id": image_id,
                        "filename": image_path.name,
                        "image": base64.b64encode(image_path.read_bytes()).decode("ascii"),
                    })
                    result = receive_message(stream, "result")
                    if result.get("id") != image_id:
                        raise ValueError("Result ID does not match the assigned image")
                    writer.writerow([image_id, image_path.name, result["text"], result["time_ms"]])

                receive_message(stream, "request")

            temp_path.replace(self.output_path)
        finally:
            temp_path.unlink(missing_ok=True)
