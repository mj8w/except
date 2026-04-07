def read_number(path):
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read()
    return parse_number(raw)


def parse_number(raw):
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("input was empty")
    return int(cleaned)


def load_value(path):
    return read_number(path)


def main():
    value = load_value("config.txt")
    return value + 1
