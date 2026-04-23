"""A test module with deeper and broader call trees."""


def validate_input(value):
    """Validate input, raises TypeError if bad type."""
    if not isinstance(value, str):
        raise TypeError("expected string")
    return value


def convert_to_int(value):
    """Convert to int, raises ValueError."""
    return int(value)


def parse_data(raw_value):
    """Parse raw input through validation and conversion."""
    validated = validate_input(raw_value)
    converted = convert_to_int(validated)
    return converted


def check_range(number):
    """Check if number is in valid range."""
    if number < 0 or number > 100:
        raise ValueError("out of range")
    return number


def process_number(raw_input):
    """Process input: parse and check range."""
    parsed = parse_data(raw_input)
    checked = check_range(parsed)
    return checked


def enrich_result(number):
    """Enrich with metadata."""
    return {"value": number, "valid": True}


def save_to_database(data):
    """Save to database (unresolved external call)."""
    database.insert(data)  # noqa: F821


def finalize(number):
    """Full pipeline: process, enrich, save."""
    processed = process_number(number)
    enriched = enrich_result(processed)
    saved = save_to_database(enriched)
    return saved


def main():
    """Entry point with multiple calls."""
    result = finalize("42")
    return result
