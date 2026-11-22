from argparse import ArgumentParser
from pathlib import Path

from src.shared import PROJECT_DIR
from src.worker_node import Worker_Node
from util.read_config import read_worker_config


def main():
    parser = ArgumentParser(description="Request PNGs from the OCR master.")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "worker_config.txt")
    args = parser.parse_args()

    try:
        master_host, master_port, n_workers = read_worker_config(args.config)
        worker_node = Worker_Node(master_host, master_port, n_workers)
        worker_node.run()
    except (EOFError, OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
