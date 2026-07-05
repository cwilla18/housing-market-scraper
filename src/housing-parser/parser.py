import model
import config
import jsonImport

import re
import threading
import requests
from bs4 import BeautifulSoup
from dataclasses import asdict
from datetime import datetime
from urllib.parse import urljoin


def build_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def get_page(url, session=None, timeout=20):
    http_session = session or requests
    return http_session.get(url, headers=build_headers(), timeout=timeout)


def post_page(url, data, session=None, headers=None, timeout=20):
    http_session = session or requests
    request_headers = build_headers()
    if headers:
        request_headers.update(headers)
    return http_session.post(url, data=data, headers=request_headers, timeout=timeout)


def parse_information():
    threads = []

    jsonImport.check_and_create_json_file()

    for site in config.site_config.items():
        thread = threading.Thread(target=crawl, args=(site,))
        threads.append(thread)

    # Start each thread
    for thread in threads:
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

def crawl(site):
    """Main orchestrator function"""
    try:
        agency = site[0]
        elements = site[1]
        url = site[1]["url"]
        
        print(f"crawl started for {agency}")
        
        if elements.get("method") == "POST":
            extracted_items = handle_post_request(agency, elements, url)
        else:
            extracted_items = handle_get_request(agency, elements, url)

        print(f"Saving following data: {extracted_items}")
        
        jsonImport.save_data_to_json(extracted_items)
    except Exception as e:
        print(f"Error occurred while crawling {site[0]}: {e}")

def handle_post_request(agency, elements, url):
    """Handle POST-based crawling with CSRF tokens"""
    session = requests.Session()
    session.headers.update(build_headers())
    response = session.get(url, timeout=20)
    #token_soup = BeautifulSoup(response.content, "html.parser")
    token_soup = get_content_for_parser(response.content)
    
    post_data = build_post_data(elements)
    csrf_token = extract_csrf_token(token_soup, elements, agency)
    if not csrf_token:
        return []
    
    post_data.extend(csrf_token)
    
    initial_response = post_page(
        elements["ajax_endpoint"],
        data=post_data,
        session=session,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    
    #soup = BeautifulSoup(initial_response.content, "html.parser")
    soup = get_content_for_parser(initial_response.content)
    extracted_items = get_items(soup, elements, agency)
    
    # Handle pagination
    pagination_type = elements.get("pagination_type")
    if pagination_type == "post_then_follow":
        extracted_items += paginate_post_then_follow(session, soup, elements, url, agency)
    else:
        extracted_items += paginate_post_pages(session, elements, post_data, agency)
    
    return extracted_items


def handle_get_request(agency, elements, url):
    """Handle GET-based crawling"""
    session = requests.Session()
    session.headers.update(build_headers())
    response = session.get(url, timeout=20)
    #if response.status_code != 200:
    if not web_request_successful(response):
        print(f"Failed to retrieve the page for {agency}. Status code: {response.status_code}")
        return []
    
    #soup = BeautifulSoup(response.content, "html.parser")
    soup = get_content_for_parser(response.content)
    extracted_items = get_items(soup, elements, agency)
    
    # Handle pagination
    pagination_type = elements.get("pagination_type")
    if pagination_type == "follow_next":
        extracted_items += paginate_follow_next(soup, elements, url, agency, session)
    else:
        extracted_items += paginate_follow_all(soup, elements, url, agency, session)
    
    return extracted_items


def build_post_data(elements):
    """Build POST data with support for list values"""
    post_data = []
    for key, val in elements["post_params"].items():
        if isinstance(val, list):
            for v in val:
                post_data.append((key, v))
        else:
            post_data.append((key, val))
    return post_data


def extract_csrf_token(soup, elements, agency):
    """Extract CSRF token (Laravel or Joomla style)"""
    if elements.get("token_type") == "joomla":
        token_input = soup.find(lambda t: t.name == "input" and 
                                t.get("type") == "hidden" and 
                                t.get("value") == "1" and 
                                len(t.get("name", "")) == 32)
        if not token_input:
            print(f"Could not find Joomla CSRF token for {agency}")
            return None
        return [(token_input["name"], "1")]
    else:
        token_input = soup.find("input", {"name": "_token"})
        if not token_input:
            print(f"Could not find CSRF token for {agency}")
            return None
        return [("_token", token_input["value"])]


def paginate_post_pages(session, elements, post_data, agency):
    """Paginate through POST responses"""
    extracted_items = []
    page_num = 2
    while True:
        paged_data = post_data + [("page", str(page_num))]
        response = post_page(
            elements["ajax_endpoint"],
            data=paged_data,
            session=session,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        if not response.content.strip():
            break

        #soup = BeautifulSoup(response.content, "html.parser")
        soup = get_content_for_parser(response.content)
        extracted_items += get_items(soup, elements, agency)
        page_num += 1
    return extracted_items


def paginate_post_then_follow(session, soup, elements, url, agency):
    """Paginate using session cookie for filter, then follow links"""
    extracted_items = []
    for page in soup.select(elements["page_class"]):
        href = page.attrs.get("href", "")
        page_url = urljoin(url, href) if (href.startswith("/") or href.startswith("?")) else href
        response = get_page(page_url, session=session)
        soup = BeautifulSoup(response.content, "html.parser")
        extracted_items += get_items(soup, elements, agency)
    return extracted_items


def paginate_follow_next(soup, elements, url, agency, session=None):
    """Follow next links until none found"""
    extracted_items = []
    while True:
        next_links = soup.select(elements["page_class"])
        if not next_links:
            break
        href = next_links[0].attrs.get("href", "")
        if not href or href in ("#", "javascript:void(0)"):
            break
        page_url = urljoin(url, href) if (href.startswith('/') or href.startswith('?')) else href
        response = get_page(page_url, session=session)
        #soup = BeautifulSoup(response.content, "html.parser")
        soup = get_content_for_parser(response.content)
        extracted_items += get_items(soup, elements, agency)
    return extracted_items


def paginate_follow_all(soup, elements, url, agency, session=None):
    """Follow all pagination links"""
    extracted_items = []
    total_pages = soup.select(elements["page_class"])
    for page in total_pages:
        href = page.attrs['href']
        page_match = re.search(r'[?&]paged?=(\d+)', href)
        if page_match and re.search(r'[?&]paged?=\d+', url):
            page_url = re.sub(r'(?<=[?&])(paged?=)\d+', f'\\g<1>{page_match.group(1)}', url)
        elif href.startswith('?') or (href.startswith('/') and not href.startswith('//')):
            page_url = urljoin(url, href)
        else:
            page_url = href
        response = get_page(page_url, session=session)
        #soup = BeautifulSoup(response.content, "html.parser")
        soup = get_content_for_parser(response.content)
        extracted_items += get_items(soup, elements, agency)
    return extracted_items

def get_items(soup, elements, agency):
    """Extract items from soup and process them"""
    extract = []
    
    if elements.get("list_box_tag"):
        items = soup.find_all(elements["list_box_tag"])
    else:
        items = soup.find_all(class_=elements["list_box"])
    
    for item in items:
        property_data = extract_property_data(item, elements, agency)
        if property_data:
            extract.append(property_data)
    
    return extract


def extract_property_data(item, elements, agency):
    """Extract all property fields from an item and handle database logic"""
    address = extract_address(item, elements)
    price = extract_price(item, elements)
    image = extract_image(item, elements)
    link = extract_property_link(item, elements)
    
    if not all([address, price, image, link]):
        return None
    
    if jsonImport.check_if_item_exists(address):
        if jsonImport.check_price_change(address, price):
            jsonImport.update_json_file_price(address, price)
        return None
    
    return model.property_model(
        date_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        agency=agency,
        address=address,
        price=price,
        old_price=0,
        image_url=image,
        house_url=link
    )


def extract_address(item, elements):
    """Extract address from item"""
    address_element = ""
    
    if elements["address"]:
        addr_container = item.find(class_=elements["address"])
        if addr_container:
            if elements["address_element"]:
                addr_tag = addr_container.find(elements["address_element"])
                if addr_tag:
                    address_element = addr_tag.text.strip()
            else:
                address_element = addr_container.text.strip()
    else:
        addr_tag = item.find(elements["address_element"])
        if addr_tag:
            address_element = addr_tag.text.strip()
    
    return address_element


def extract_price(item, elements):
    """Extract and process price from item"""
    price_elements = item.find_all(class_=elements["price"])
    if not price_elements:
        return ""
    
    raw_price = item.find(class_=elements["price"]).text.strip().replace("\u00a3", "")
    
    if elements.get("price_regex"):
        match = re.search(elements["price_regex"], raw_price)
        return match.group(0) if match else raw_price
    
    return raw_price


def extract_image(item, elements):
    """Extract image URL from item"""
    image_element = ""
    
    if elements.get("image_select"):
        img_tag = item.select_one(elements["image_select"])
        if img_tag and elements['image_attrs'] in img_tag.attrs:
            image_element = img_tag.attrs[elements['image_attrs']]
    elif elements["image_url"]:
        image_containers = item.find_all(class_=elements["image_url"])
        if image_containers:
            img_tag = item.find(class_=elements["image_url"]).find(elements["image_element"])
            if img_tag and elements['image_attrs'] in img_tag.attrs:
                image_element = img_tag.attrs[elements['image_attrs']]
    
    return image_element


def extract_property_link(item, elements):
    """Extract property link from item"""
    link_elements = item.find_all(elements["house_element"])
    if not link_elements:
        return ""
    
    link_tag = item.find(elements["house_element"])
    if link_tag and elements['house_attrs'] in link_tag.attrs:
        return link_tag.attrs[elements['house_attrs']]
    
    return ""


def web_request_successful(response):
    return response.status_code == 200

def get_content_for_parser(content):
    return BeautifulSoup(content, "html.parser")
