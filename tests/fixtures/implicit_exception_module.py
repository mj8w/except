def parse_count(payload):
    return int(payload["count"])


def main():
    payload = {"count": "abc"}
    return parse_count(payload)
