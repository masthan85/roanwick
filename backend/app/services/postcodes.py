import re

from app.core.errors import Unprocessable

_UK = re.compile(r"^([A-Z]{1,2}[0-9][A-Z0-9]?)\s*([0-9][A-Z]{2})$")


def normalise_postcode(raw: str) -> tuple[str, str]:
    """Return (formatted postcode, outward code) or raise a validation error."""
    compact = re.sub(r"\s+", "", raw or "").upper()
    m = _UK.match(compact[:-3] + " " + compact[-3:]) if len(compact) >= 5 else None
    if not m:
        raise Unprocessable("Please enter a full UK postcode, for example SW11 1AB.", code="invalid_postcode")
    return f"{m.group(1)} {m.group(2)}", m.group(1)
