def leaf():
    raise ValueError("bad value")


def wrapper():
    try:
        leaf()
    except ValueError:
        return "default"
    return "live"


def main():
    return wrapper()
