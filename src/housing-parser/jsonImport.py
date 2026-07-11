import json
import logging
import os
import tempfile
from dataclasses import asdict

import config
import model
import constValues as const

logger = logging.getLogger(__name__)


def _data_path():
    return os.path.join(
        config.general["base_dir"],
        config.general["file_type"],
        config.general["file_name"],
    )


def load_data():
    path = _data_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return json.loads(content) if content else []


def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _normalize(record):
    record[const.PRICE] = model.parse_price(record.get(const.PRICE)) or 0
    record["old_price"] = model.parse_price(record.get("old_price")) or 0
    record.setdefault("id", 0)
    record.setdefault("active", True)
    return record


def sync(scraped_items):
    existing = [_normalize(r) for r in load_data()]
    by_key = {r.get("house_url"): r for r in existing}
    next_id = max((r.get("id", 0) for r in existing), default=0) + 1

    seen_keys = set()
    new_count = price_changes = 0
    for obj in scraped_items:
        key = obj.house_url
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)

        stored = by_key.get(key)
        if stored is None:
            record = asdict(obj)
            record["id"] = next_id
            record["active"] = True
            next_id += 1
            existing.append(record)
            by_key[key] = record
            new_count += 1
        else:
            stored["active"] = True
            updated_fields = asdict(obj)
            updated_fields.pop("id", None)
            updated_fields.pop("active", None)
            stored.update(updated_fields)
            if stored.get(const.PRICE) != obj.price:
                stored["old_price"] = stored.get(const.PRICE, 0)
                stored[const.PRICE] = obj.price
                price_changes += 1

    # Reconcile visibility: anything stored but not seen this run is inactive.
    # Guard against a fully-failed scrape wiping every item to inactive.
    deactivated = 0
    if seen_keys:
        for record in existing:
            if record.get("house_url") not in seen_keys and record.get("active"):
                record["active"] = False
                deactivated += 1
    else:
        logger.warning("No listings scraped this run; skipping inactive reconciliation.")

    _atomic_write(_data_path(), existing)
    logger.info(
        "sync complete: %d total, %d new, %d price changes, %d deactivated",
        len(existing), new_count, price_changes, deactivated,
    )
    return existing
