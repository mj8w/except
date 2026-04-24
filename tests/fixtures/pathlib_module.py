from pathlib import Path


def read_config(path):
    config_path = Path(path)
    return config_path.read_text(encoding="utf-8")


def main():
    return read_config("settings.txt")
