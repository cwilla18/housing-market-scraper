import json
import os
from dataclasses import asdict

import config


def check_and_create_json_file(json_save_path=None):
    if json_save_path is None:
        json_save_path = os.path.join(
            config.general["base_dir"],
            config.general["file_type"],
            config.general["file_name"],
        )

    if os.path.exists(json_save_path):
        with open(json_save_path, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if not content:
                return []
            return json.loads(content)

    print(f"{json_save_path} not found. Creating a new file.")
    os.makedirs(os.path.dirname(json_save_path), exist_ok=True)
    with open(json_save_path, "w", encoding="utf-8") as file:
        json.dump([], file)
    return []


def save_data_to_json(data):
    json_save_path = os.path.join(
        config.general["base_dir"],
        config.general["file_type"],
        config.general["file_name"],
    )
    existing_data = check_and_create_json_file(json_save_path)

    existing_data.extend(asdict(obj) for obj in data)

    with open(json_save_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=4)


def check_if_item_exists(item_address):
    json_save_path = os.path.join(
        config.general["base_dir"],
        config.general["file_type"],
        config.general["file_name"],
    )
    file = get_json_file(json_save_path)

    for item in file:
        if item.get("address") == item_address:
            return True

    return False


def check_price_change(item_address, new_price):
    json_save_path = os.path.join(
        config.general["base_dir"],
        config.general["file_type"],
        config.general["file_name"],
    )
    file = get_json_file(json_save_path)

    for item in file:
        if item.get("address") == item_address:
            return item.get("price") != new_price

    return False


def update_json_file_price(item_address, new_price):
    json_save_path = os.path.join(
        config.general["base_dir"],
        config.general["file_type"],
        config.general["file_name"],
    )
    file = get_json_file(json_save_path)

    for item in file:
        if item.get("address") == item_address:
            if item.get("price") != new_price:
                item["old_price"] = item.get("price")
                item["price"] = new_price
                with open(json_save_path, "w", encoding="utf-8") as f:
                    json.dump(file, f, indent=4)
                return True
            return False

    return False


def get_json_file(json_save_path):
    return check_and_create_json_file(json_save_path)