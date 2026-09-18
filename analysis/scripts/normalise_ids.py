"""Compare map builds by numbering random element IDs and verified worker stamps."""

import re
import sys
from pathlib import Path

seen: dict[int, dict[str, int]] = {32: {}, 16: {}}


def ordinal(match: re.Match[str]) -> str:
    """Give each ID or stamp its first-seen ordinal within its own counter."""
    value = match[0]
    counter = seen[len(value)]
    prefix = "ID" if len(value) == 32 else "STAMP"
    return f"{prefix}{counter.setdefault(value, len(counter))}"


text = re.sub(r"(?<![0-9a-f])(?:[0-9a-f]{32}|[0-9a-f]{16})(?![0-9a-f])", ordinal, Path(sys.argv[1]).read_text(encoding="utf-8"))
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(text, encoding="utf-8")
else:
    sys.stdout.write(text)
