"""Three-valued applicability evaluation over confirmed facts."""


def condition_value(condition, facts, _depth=0):
    if not isinstance(condition, dict) or _depth > 12:
        return None
    if not condition:
        return True
    if "all" in condition or "any" in condition:
        op = "all" if "all" in condition else "any"
        children = condition[op]
        if set(condition) != {op} or not isinstance(children, list) or not children:
            return None
        values = [condition_value(c, facts, _depth + 1) for c in children]
        if op == "any":
            return True if True in values else (None if None in values else False)
        return False if False in values else (None if None in values else True)
    field, op = condition.get("field"), condition.get("op", "eq")
    if not isinstance(field, str) or field not in facts or "value" not in condition:
        return None
    actual, expected = facts[field], condition.get("value")
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in" and isinstance(expected, list):
        return actual in expected
    return None
