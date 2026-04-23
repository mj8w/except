"""A test module with implicit exception operations."""


def divide_by_value(dividend, divisor):
    """Divide two numbers - could raise ZeroDivisionError."""
    result = dividend / divisor
    return result


def access_list_item(items, index):
    """Access list by index - could raise IndexError."""
    return items[index]


def access_dict_item(data, key):
    """Access dict by key - could raise KeyError."""
    return data[key]


def process_config(config_list):
    """Process configuration - multiple implicit exceptions."""
    timeout = config_list[0]
    success_rate = divide_by_value(100, timeout)
    return success_rate


def fetch_setting(config_dict, setting_name):
    """Fetch setting from dict - KeyError possible."""
    value = access_dict_item(config_dict, setting_name)
    return value * 2


def main():
    """Entry point - calls functions with implicit exceptions."""
    config = {"timeout": 0, "retries": 3}
    setting = fetch_setting(config, "timeout")
    return setting
