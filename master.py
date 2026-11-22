from argparse import ArgumentParser
from pathlib import Path

from src.ocr_master import OCR_Master
from src.shared import PROJECT_DIR, RESULTS_DIR
from util.read_config import read_master_config


def main():
    parser = ArgumentParser(description="Send a batch of PNGs to an OCR worker.")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "master_config.txt")
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_DIR / "ocr_results.csv",
        help="Path for the completed OCR results CSV.",
    )
    parser.add_argument(
        "--worker-timeout",
        type=float,
        default=60.0,
        help="Socket timeout for worker communication in seconds (default: 60).",
    )
    args = parser.parse_args()

    try:
        image_dir, port = read_master_config(args.config)
        master = OCR_Master(image_dir, port, args.output, worker_timeout=args.worker_timeout)
        master.run()
    except (EOFError, OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
