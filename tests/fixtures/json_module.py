from json import loads


def parse_payload(payload):
    return loads(payload)


def main():
    return parse_payload('{"count": 1}')
