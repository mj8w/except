from requests import get


def fetch_status(url):
    return get(url, timeout=5)


def main():
    return fetch_status("https://example.com")
