import time

import pytesseract
from PIL import ImageFilter, ImageOps

from src.shared import MODEL_DIR, NON_LETTER_EDGES


def recognize_image(image):
    # Include preprocessing and OCR in the reported time.
    start_time = time.perf_counter_ns()
    grayscale = ImageOps.grayscale(image)
    denoised = grayscale.filter(ImageFilter.MedianFilter(3))

    text = pytesseract.image_to_string(
        denoised,
        lang="eng",
        # Use automatic page layout, as in MP1.
        config=f'--tessdata-dir "{MODEL_DIR}" --psm 3',
        timeout=30,
    )
    elapsed_ns = time.perf_counter_ns() - start_time
    return NON_LETTER_EDGES.sub("", text), elapsed_ns / 1_000_000
