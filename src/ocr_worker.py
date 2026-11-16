# OCR Worker class: This handles one process of OCR

from multiprocessing import Process

from src.recognition import recognize_image
from src.shared import STOP

class OCR_Worker(Process):

    def __init__(self, worker_id, image_queue, result_queue):
        # Name the process after worker_id, so workers are 1 to n instead of
        # Python's automatic process number
        super().__init__(name=f"OCR_Worker-{worker_id}")
        self.worker_id = worker_id
        self.image_queue = image_queue
        self.result_queue = result_queue

    def recognize_image(self, image):
        return recognize_image(image)
    
    def run(self):
        print(f"Worker {self.worker_id} started.")
        worker_name = self.name

        while True:
            item = self.image_queue.get()

            if item is STOP:
                break

            image_id, filename, image = item

            try:
                text, elapsed_ms = self.recognize_image(image)
            except Exception as error:
                # Report the failed image and move on, so this worker still reaches its STOP
                print(f"{worker_name} failed on {filename}: {error}")
                continue

            print(f"{image_id},{filename},{text},{worker_name},{elapsed_ms:.4f}ms")
            # Save time as a number, so it can be summed and averaged
            self.result_queue.put([image_id, filename, text, worker_name, round(elapsed_ms, 4)])
