class ParseFailedError(Exception):
    pass


def parse_number(raw):
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("empty input")
    return int(cleaned)


def read_number(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()
        return parse_number(raw)
    except ValueError:
        return 0


def ratio_from_file(path, divisor):
    number = read_number(path)
    return number / divisor


def main():
    return ratio_from_file("missing.txt", 0)
