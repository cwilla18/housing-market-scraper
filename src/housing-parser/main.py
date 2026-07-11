import logging
import os
import time

import requests

import config
import jsonImport
import scraper


for _var in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
    _val = os.environ.get(_var)
    if _val:
        _expanded = os.path.expandvars(_val)
        if os.path.exists(_expanded):
            os.environ[_var] = _expanded
        else:
            del os.environ[_var]

logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(threadName)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def check_internet_connection():
    if config.general["internet_check"] is False:
        return True

    host = config.general["internet_host"]
    timeout = config.general["internet_timeout"]
    retries = config.general["internet_retries"]

    for attempt in range(1, retries + 1):
        try:
            response = requests.head(host, timeout=timeout)
            if response.status_code == 200:
                logger.info("Connected to the internet successfully.")
                return True
            logger.warning(
                "Unexpected status code %s from %s", response.status_code, host
            )
        except requests.exceptions.RequestException as e:
            logger.warning("Connection attempt %s/%s failed: %s", attempt, retries, e)

        if attempt < retries:
            time.sleep(timeout)

    logger.error("Failed to connect to the internet after %s attempts.", retries)
    return False


def main():
    if not check_internet_connection():
        logger.error("No internet connection. Exiting the application.")
        return 1

    logger.info("Internet connection found. Begin parsing")
    items = scraper.scrape_all_sites()
    jsonImport.sync(items)
    logger.info("Property agencies have been crawled. Application is closing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
