from argparse import ArgumentParser
from pathlib import Path

from src.ocr_master import OCR_Master
from src.shared import PROJECT_DIR
from util.read_config import read_master_config


def main():
    parser = ArgumentParser(description="Send one PNG to an OCR worker.")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "master_config.txt")
    args = parser.parse_args()

    try:
        image_dir, port = read_master_config(args.config)
        master = OCR_Master(image_dir, port)
        master.run()
    except (EOFError, OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
