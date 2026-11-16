from argparse import ArgumentParser
from pathlib import Path

from src.shared import PROJECT_DIR
from util.read_config import read_master_config


def main():
    parser = ArgumentParser(description="Load the distributed OCR master configuration.")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "master_config.txt")
    args = parser.parse_args()

    try:
        image_dir, port = read_master_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(f"image_dir={image_dir}")
    print(f"port={port}")


if __name__ == "__main__":
    main()
