"""Text normalization shared by deterministic review checks."""

import re


def norm(value):
    return re.sub(r"\s+", "", str(value))
