from dataclasses import dataclass

@dataclass
class property_model: 
    id: int
    date_time: str
    agency: str
    address: str
    price: float
    old_price: float
    image_url: str
    house_url: str
    active: bool