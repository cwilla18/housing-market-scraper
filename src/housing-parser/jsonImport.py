import json
import os
import threading
from dataclasses import asdict

import config

# Lock to serialize file read/write and id assignment across threads
_file_lock = threading.Lock()
_next_id = None


def check_and_create_json_file(json_save_path = None):
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

    with _file_lock:
        existing_data = check_and_create_json_file(json_save_path)

        existing_ids = [item.get("id") for item in existing_data if isinstance(item, dict) and "id" in item]
        try:
            numeric_ids = [int(i) for i in existing_ids]
            next_id = max(numeric_ids) + 1 if numeric_ids else 1
        except Exception:
            next_id = len(existing_data) + 1

        existing_addresses = {
            item.get("address"): item
            for item in existing_data
            if isinstance(item, dict) and item.get("address")
        }

        new_entries = []
        seen_addresses = set()
        for obj in data:
            entry = asdict(obj)
            address = entry.get("address")
            if not address or address in seen_addresses:
                continue
            seen_addresses.add(address)

            if address in existing_addresses:
                existing_entry = existing_addresses[address]
                if entry.get("price") != existing_entry.get("price"):
                    existing_entry["old_price"] = existing_entry.get("price", 0)
                    existing_entry["price"] = entry.get("price")
                continue

            entry_id = entry.get("id")
            try:
                entry_id = int(entry_id) if entry_id is not None else None
            except Exception:
                entry_id = None

            if entry_id is None or entry_id in numeric_ids:
                entry["id"] = next_id
                next_id += 1
            else:
                entry["id"] = entry_id
                numeric_ids.append(entry_id)

            new_entries.append(entry)

        existing_data.extend(new_entries)

        with open(json_save_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4)

def get_json_file_count(json_save_path: str = None, reserve: int = 1):
    global _next_id

    with _file_lock:
        if _next_id is None:
            data = get_json_file(json_save_path)
            if not data:
                _next_id = 1
            else:
                ids = [item.get("id") for item in data if isinstance(item, dict) and "id" in item]
                try:
                    numeric_ids = [int(i) for i in ids]
                    _next_id = max(numeric_ids) + 1 if numeric_ids else 1
                except Exception:
                    _next_id = len(data) + 1

        start_id = _next_id
        _next_id += max(1, int(reserve))
        return start_id

def check_if_item_exists(item_address):
    json_save_path = os.path.join(
        config.general["base_dir"],
        config.general["file_type"],
        config.general["file_name"],
    )
    with _file_lock:
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
    with _file_lock:
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
    with _file_lock:
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