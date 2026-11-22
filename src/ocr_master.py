import base64
import csv
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, Queue
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

        tasks = Queue()
        for task in enumerate(image_paths, start=1):
            tasks.put(task)

        with socket.create_server(("127.0.0.1", self.port)) as server:
            server.settimeout(0.1)
            print(f"Listening on 127.0.0.1:{self.port}", flush=True)
            rows = self._collect_results(server, tasks, len(image_paths))

        self._write_results(rows)
        print(f"Saved {len(image_paths)} OCR results to {self.output_path}")

    def _collect_results(self, server, tasks, total_tasks):
        rows = []
        workers = {}
        with ThreadPoolExecutor() as executor:
            try:
                while True:
                    for future in list(workers):
                        if future.done():
                            rows.extend(future.result())
                            del workers[future]

                    try:
                        connection, _ = server.accept()
                    except TimeoutError:
                        # Keep serving connections already waiting in the listen queue.
                        if len(rows) == total_tasks and not workers:
                            return rows
                    else:
                        workers[executor.submit(self._serve_worker, connection, tasks)] = connection
            finally:
                # Unblock other handlers if one fails so a partial batch is never published.
                for connection in workers.values():
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

    def _serve_worker(self, connection, tasks):
        rows = []
        with connection, connection.makefile("rwb") as stream:
            while True:
                receive_message(stream, "request")
                try:
                    image_id, image_path = tasks.get_nowait()
                except Empty:
                    send_message(stream, {"type": "no_tasks"})
                    return rows

                send_message(stream, {
                    "type": "task",
                    "id": image_id,
                    "filename": image_path.name,
                    "image": base64.b64encode(image_path.read_bytes()).decode("ascii"),
                })
                result = receive_message(stream, "result")
                if result.get("id") != image_id:
                    raise ValueError("Result ID does not match the assigned image")
                rows.append((image_id, image_path.name, result["text"], result["time_ms"]))

    def _write_results(self, rows):
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

                writer.writerows(sorted(rows))

            temp_path.replace(self.output_path)
        finally:
            temp_path.unlink(missing_ok=True)
