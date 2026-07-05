from dataclasses import dataclass

@dataclass
class property_model: 
    date_time: str
    agency: str
    address: str
    price: float
    old_price: float
    image_url: str
    house_url: str