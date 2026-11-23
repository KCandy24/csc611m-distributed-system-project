import base64
import socket
from contextlib import ExitStack
from io import BytesIO
from multiprocessing import get_context
from multiprocessing.connection import wait
from os import getpid

from PIL import Image

from src.protocol import receive_message, send_message
from src.recognition import recognize_image


def _process_tasks(connection):
    with connection, connection.makefile("rwb") as stream:
        while True:
            send_message(stream, {"type": "request"})
            task = receive_message(stream, "task", "shutdown")
            if task["type"] == "shutdown":
                return

            image_bytes = base64.b64decode(task["image"], validate=True)
            with Image.open(BytesIO(image_bytes)) as image:
                text, time_ms = recognize_image(image)

            send_message(stream, {
                "type": "result",
                "id": task["id"],
                "text": text,
                "time_ms": round(time_ms, 4),
            })
            print(f"Worker {getpid()} processed {task['filename']}", flush=True)


class Worker_Node:
    def __init__(self, master_host, master_port, n_workers):
        self.master_host = master_host
        self.master_port = master_port
        self.n_workers = n_workers

    def run(self):
        address = (self.master_host, self.master_port)
        if self.n_workers == 1:
            _process_tasks(socket.create_connection(address))
            return

        context = get_context("spawn")
        processes = {}
        try:
            with ExitStack() as sockets:
                # Register every connection before a process can finish a short batch.
                connections = [
                    sockets.enter_context(socket.create_connection(address))
                    for _ in range(self.n_workers)
                ]
                for connection in connections:
                    process = context.Process(target=_process_tasks, args=(connection,))
                    process.start()
                    processes[process.sentinel] = process
                    connection.close()

            while processes:
                for sentinel in wait(processes):
                    process = processes.pop(sentinel)
                    process.join()
                    if process.exitcode != 0:
                        raise ValueError(f"OCR process {process.pid} exited with code {process.exitcode}")
        finally:
            for process in processes.values():
                if process.is_alive():
                    process.terminate()
            for process in processes.values():
                process.join()
