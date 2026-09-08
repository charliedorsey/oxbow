import json


def normalize_line(line):
    parts = [part.strip() for part in line.split("|")]
    if len(parts) != 3:
        raise ValueError("expected exactly three pipe-delimited fields")
    return {"title": parts[0], "owner": parts[1], "status": parts[2]}


def normalize_text(text):
    return [normalize_line(line) for line in text.splitlines() if line.strip()]


def to_json_lines(text):
    return "\n".join(json.dumps(row, sort_keys=True) for row in normalize_text(text)) + "\n"
