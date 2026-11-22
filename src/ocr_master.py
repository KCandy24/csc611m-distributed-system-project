import base64
import csv
import socket
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

from src.protocol import receive_message, send_message


class _Batch:
    def __init__(self, image_paths):
        self._pending = deque(enumerate(image_paths, start=1))
        self._total = len(image_paths)
        self._aborted = False
        self._condition = Condition()
        self.rows = []

    def next_task(self):
        with self._condition:
            self._condition.wait_for(
                lambda: self._pending or len(self.rows) == self._total or self._aborted
            )
            if self._aborted:
                raise EOFError("OCR batch aborted")
            if self._pending:
                return self._pending.popleft()
            return None

    def record_result(self, row):
        with self._condition:
            self.rows.append(row)
            if len(self.rows) == self._total:
                self._condition.notify_all()

    def is_complete(self):
        with self._condition:
            return len(self.rows) == self._total

    def abort(self):
        with self._condition:
            self._aborted = True
            self._condition.notify_all()


class OCR_Master:
    def __init__(self, image_dir, port, output_path):
        self.image_dir = image_dir
        self.port = port
        self.output_path = output_path

    def run(self):
        image_paths = sorted(path for path in self.image_dir.glob("*.png") if path.is_file())
        if not image_paths:
            raise ValueError(f"No PNG images found in {self.image_dir}")

        batch = _Batch(image_paths)
        with socket.create_server(("127.0.0.1", self.port)) as server:
            server.settimeout(0.1)
            print(f"Listening on 127.0.0.1:{self.port}", flush=True)
            self._serve_batch(server, batch)

        self._write_results(batch.rows)
        print(f"Saved {len(image_paths)} OCR results to {self.output_path}")

    def _serve_batch(self, server, batch):
        workers = {}
        with ThreadPoolExecutor() as executor:
            try:
                while True:
                    for future in list(workers):
                        if future.done():
                            future.result()
                            del workers[future]

                    try:
                        connection, _ = server.accept()
                    except TimeoutError:
                        # Keep serving connections already waiting in the listen queue.
                        if not workers and batch.is_complete():
                            return
                    else:
                        workers[executor.submit(self._serve_worker, connection, batch)] = connection
            finally:
                # Unblock other handlers if one fails so a partial batch is never published.
                if workers:
                    batch.abort()
                for connection in workers.values():
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

    def _serve_worker(self, connection, batch):
        with connection, connection.makefile("rwb") as stream:
            while True:
                receive_message(stream, "request")
                task = batch.next_task()
                if task is None:
                    send_message(stream, {"type": "shutdown"})
                    return

                image_id, image_path = task
                send_message(stream, {
                    "type": "task",
                    "id": image_id,
                    "filename": image_path.name,
                    "image": base64.b64encode(image_path.read_bytes()).decode("ascii"),
                })
                result = receive_message(stream, "result")
                if result.get("id") != image_id:
                    raise ValueError("Result ID does not match the assigned image")
                batch.record_result((image_id, image_path.name, result["text"], result["time_ms"]))

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
