import base64
import csv
import socket
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from math import inf
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

from src.protocol import receive_message, send_message


class _Batch:
    def __init__(self, image_paths):
        self._pending = deque(enumerate(image_paths, start=1))
        self._in_progress = {}
        self._total = len(image_paths)
        self._aborted = False
        self._condition = Condition()
        self.rows = []

    def next_task(self, connection):
        with self._condition:
            self._condition.wait_for(
                lambda: self._pending or len(self.rows) == self._total or self._aborted
            )
            if self._aborted:
                raise EOFError("OCR batch aborted")
            if self._pending:
                task = self._pending.popleft()
                self._in_progress[connection] = task
                return task
            return None

    def record_result(self, connection, result):
        with self._condition:
            image_id, image_path = self._in_progress[connection]
            result_id = result.get("id")
            if type(result_id) is not int or result_id != image_id:
                raise ValueError("Result ID does not match the assigned image")
            text = result.get("text")
            time_ms = result.get("time_ms")
            if not isinstance(text, str) or type(time_ms) not in (int, float) or not 0 <= time_ms < inf:
                raise ValueError("Result must contain text and a valid processing time")

            self.rows.append((image_id, image_path.name, text, time_ms))
            del self._in_progress[connection]
            if len(self.rows) == self._total:
                self._condition.notify_all()

    def requeue(self, connection):
        with self._condition:
            task = self._in_progress.pop(connection, None)
            if task is not None:
                self._pending.appendleft(task)
                self._condition.notify()
            return task

    def is_complete(self):
        with self._condition:
            return len(self.rows) == self._total

    def abort(self):
        with self._condition:
            self._aborted = True
            self._condition.notify_all()


class OCR_Master:
    def __init__(self, image_dir, port, output_path, worker_timeout=60.0):
        if not 0 < worker_timeout < inf:
            raise ValueError("Worker timeout must be a positive, finite number")
        self.image_dir = image_dir
        self.port = port
        self.output_path = output_path
        self.worker_timeout = worker_timeout

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
                        connection, address = server.accept()
                    except TimeoutError:
                        # Keep serving connections already waiting in the listen queue.
                        if not workers and batch.is_complete():
                            return
                    else:
                        future = executor.submit(self._serve_worker, connection, address, batch)
                        workers[future] = connection
            finally:
                # Unblock other handlers if one fails so a partial batch is never published.
                if workers:
                    batch.abort()
                for connection in workers.values():
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

    def _serve_worker(self, connection, address, batch):
        try:
            with connection, connection.makefile("rwb") as stream:
                connection.settimeout(self.worker_timeout)
                while True:
                    receive_message(stream, "request")
                    task = batch.next_task(connection)
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
                    batch.record_result(connection, receive_message(stream, "result"))
        except (ConnectionError, EOFError, TimeoutError, ValueError) as error:
            # The connection is closed before another worker can claim this image.
            task = batch.requeue(connection)
            if task is not None:
                _, image_path = task
                print(f"Requeued {image_path.name} from {address}: {error}", flush=True)

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
