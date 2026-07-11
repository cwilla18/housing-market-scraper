import re
from dataclasses import dataclass


@dataclass
class PropertyModel:
    date_time: str
    agency: str
    address: str
    price: int
    old_price: int
    image_url: str
    house_url: str
    # id is assigned at save time (see jsonImport.sync); active defaults to True
    # because a freshly-scraped listing is, by definition, currently live.
    id: int = 0
    active: bool = True


def parse_price(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    # Drop any decimal portion, then strip currency symbols, commas and spaces.
    digits = re.sub(r"[^\d]", "", str(raw).split(".")[0])
    return int(digits) if digits else None
