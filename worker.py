from argparse import ArgumentParser
from pathlib import Path

from src.shared import PROJECT_DIR
from util.read_config import read_worker_config


def main():
    parser = ArgumentParser(description="Load the distributed OCR worker configuration.")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "worker_config.txt")
    args = parser.parse_args()

    try:
        master_host, master_port, n_workers = read_worker_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(f"master_host={master_host}")
    print(f"master_port={master_port}")
    print(f"n_workers={n_workers}")


if __name__ == "__main__":
    main()
