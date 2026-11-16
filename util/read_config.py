from pathlib import Path
from src.shared import PROJECT_DIR


def _read_settings(config_path, required_keys):
    settings = {}
    for line in config_path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")

        if not separator:
            raise ValueError(f"Line is not key=value: {line!r}")
        settings[key.strip()] = value.strip()

    for key in required_keys:
        if key not in settings:
            raise ValueError(f"{config_path.name} is missing {key}")

    return settings


def _read_image_dir(value):
    # Resolve relative image paths from the project folder.
    image_dir = Path(value).expanduser()
    if not image_dir.is_absolute():
        image_dir = PROJECT_DIR / image_dir
    if not image_dir.is_dir():
        raise ValueError(f"image_dir is not a folder: {image_dir}")
    return image_dir


def _read_worker_count(value):
    n_workers = int(value)
    if n_workers < 1:
        raise ValueError("n_workers must be at least 1")
    return n_workers


def _read_port(value, key):
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError(f"{key} must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError(f"{key} must be between 1 and 65535")
    return port


def read_config(config_path):
    settings = _read_settings(config_path, ("image_dir", "n_workers"))
    image_dir = _read_image_dir(settings["image_dir"])
    n_workers = _read_worker_count(settings["n_workers"])
    return image_dir, n_workers


def read_master_config(config_path):
    settings = _read_settings(config_path, ("image_dir", "port"))
    image_dir_value = settings["image_dir"]
    if not image_dir_value:
        raise ValueError("image_dir must not be empty")
    image_dir = _read_image_dir(image_dir_value)
    port = _read_port(settings["port"], "port")
    return image_dir, port


def read_worker_config(config_path):
    settings = _read_settings(config_path, ("master_host", "master_port", "n_workers"))
    master_host = settings["master_host"]
    if not master_host:
        raise ValueError("master_host must not be empty")
    master_port = _read_port(settings["master_port"], "master_port")
    n_workers = _read_worker_count(settings["n_workers"])
    return master_host, master_port, n_workers
