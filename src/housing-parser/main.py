import config
import parser
import requests
from time import time

def check_internet_connection():
    if config.general["internet_check"] is False:
        return True
    
    host = config.general["internet_host"]
    port = config.general["internet_port"]
    timeout = config.general["internet_timeout"]
    retires = config.general["internet_retries"]
    timeout = config.general["internet_timeout"]

    for _ in range(retires):
        try:
            response = requests.head(host)

            if response.status_code != 200:
                print(f"http response code was not 200. Server returning: {response.status_code}")

            print("Connected to the internet successfully.")
            return True
        except OSError:
            print(f"Retry after {timeout} seconds")
            time.sleep(timeout)
    
    print("Failed to connect to the internet after 3 attempts.")
    return False


if check_internet_connection():
    try:
        print("Internet connection found. Begin parsing")
        parser.parse_information()
        print("Property agencies have been crawled. Application is closing")
    except Exception as e:
        print(f"Exception: {e}")
else:
    print("Exiting the application.")
    exit(1)