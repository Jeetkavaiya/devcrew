import re

_NAME_LABEL_PATTERN = re.compile(
    r"function\s*name\s*[:\-]\s*`?([a-zA-Z_][a-zA-Z0-9_]*)`?",
    re.IGNORECASE,
)
_DEF_PATTERN = re.compile(r"\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")


def extract_function_name(spec: str) -> str:
    """Extract the target function name from a Planner spec.

    Single source of truth used by both coder_node and tester_node, so the
    two agents can never independently guess two different names for the
    same function. Previously tester.py had its own copy of this logic and
    coder.py had none at all (it just let the model free-name the function
    from prose) -- that let a Coder implementation and Tester's import line
    silently diverge whenever the Planner's spec didn't state the name in a
    form the old regex happened to catch.

    The Planner's system prompt now contractually guarantees a
    "Function name: <name>" line as the first line of the spec, so that is
    checked first. The `def name(...)` signature match and the old fallback
    label match are kept as defensive fallbacks for specs that predate the
    contract or come from a differently-prompted Planner variant.

    Falls back to the literal placeholder "solution_function" only if none
    of the above match -- at that point the spec itself is malformed
    relative to the Planner's contract, and this is a last resort, not an
    expected path.
    """
    label_match = _NAME_LABEL_PATTERN.search(spec)
    if label_match:
        return label_match.group(1)

    def_match = _DEF_PATTERN.search(spec)
    if def_match:
        return def_match.group(1)

    return "solution_function"