import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config
import model
import constValues as const

logger = logging.getLogger(__name__)


def get_page(url, session = None, timeout=20):
    http_session = session or requests
    return http_session.get(url, headers = config.build_headers(), timeout=timeout)


def post_page(url, data, session=None, headers=None, timeout=20):
    http_session = session or requests
    request_headers = config.build_headers()
    if headers:
        request_headers.update(headers)
    return http_session.post(url, data=data, headers=request_headers, timeout=timeout)


def scrape_all_sites():
    sites = list(config.site_config.items())
    all_items = []
    with ThreadPoolExecutor(max_workers = max(1, len(sites))) as executor:
        for items in executor.map(crawl, sites):
            all_items.extend(items)
    return all_items


def crawl(site):
    agency, elements = site
    url = elements[const.URL]
    logger.info("crawl started for %s", agency)
    try:
        if elements.get("method") == "POST":
            items = handle_post_request(agency, elements, url)
        else:
            items = handle_get_request(agency, elements, url)
        logger.info("crawl finished for %s: %d listings", agency, len(items))
        return items
    except Exception as e:
        logger.exception("Error occurred while crawling %s: %s", agency, e)
        return []


def handle_post_request(agency, elements, url):
    session = requests.Session()
    session.headers.update(config.build_headers())
    response = session.get(url, timeout=20)
    token_soup = get_content_for_parser(response.content)

    post_data = build_post_data(elements)
    csrf_token = extract_csrf_token(token_soup, elements, agency)
    if not csrf_token:
        return []

    post_data.extend(csrf_token)

    initial_response = post_page(
        elements[const.AJAX_ENDPOINT],
        data = post_data,
        session = session,
        headers = {const.X_REQUESTED_WITH: const.XML_HTTP_REQUEST},
    )

    soup = get_content_for_parser(initial_response.content)

    # Handle pagination
    pagination_type = elements.get(const.PAGINATION_TYPE)
    if pagination_type == "post_then_follow":
        # paginate_post_then_follow fetches ALL pages via the session cookie (including page 1),
        # so don't call get_items on the initial response to avoid duplicating page 1 items.
        extracted_items = paginate_post_then_follow(session, soup, elements, url, agency)
    else:
        extracted_items = get_items(soup, elements, agency)
        extracted_items += paginate_post_pages(session, elements, post_data, agency)

    return extracted_items


def handle_get_request(agency, elements, url):
    session = requests.Session()
    session.headers.update(config.build_headers())
    response = session.get(url, timeout = 20)
    if not web_request_successful(response):
        logger.warning(
            "Failed to retrieve the page for %s. Status code: %s",
            agency,
            response.status_code,
        )
        return []

    soup = get_content_for_parser(response.content)
    extracted_items = get_items(soup, elements, agency)

    # Handle pagination
    pagination_type = elements.get(const.PAGINATION_TYPE)
    if pagination_type == "follow_next":
        extracted_items += paginate_follow_next(soup, elements, url, agency, session)
    else:
        extracted_items += paginate_follow_all(soup, elements, url, agency, session)

    return extracted_items


def build_post_data(elements):
    post_data = []
    for key, val in elements[const.POST_PARAMS].items():
        if isinstance(val, list):
            for v in val:
                post_data.append((key, v))
        else:
            post_data.append((key, val))
    return post_data


def extract_csrf_token(soup, elements, agency):
    if elements.get("token_type") == "joomla":
        token_input = soup.find(lambda t: t.name == const.INPUT and
                                t.get(const.TYPE) == "hidden" and
                                t.get(const.VALUE) == "1" and
                                len(t.get(const.NAME, "")) == 32)
        if not token_input:
            logger.warning("Could not find Joomla CSRF token for %s", agency)
            return None
        return [(token_input[const.NAME], "1")]
    else:
        token_input = soup.find(const.INPUT, {const.NAME: "_token"})
        if not token_input:
            logger.warning("Could not find CSRF token for %s", agency)
            return None
        return [("_token", token_input[const.VALUE])]


def paginate_post_pages(session, elements, post_data, agency):
    extracted_items = []
    page_num = 2
    while True:
        paged_data = post_data + [(const.PAGE, str(page_num))]
        response = post_page(
            elements[const.AJAX_ENDPOINT],
            data = paged_data,
            session = session,
            headers = {const.X_REQUESTED_WITH: const.XML_HTTP_REQUEST},
        )
        if not response.content.strip():
            break

        soup = get_content_for_parser(response.content)
        new_items = get_items(soup, elements, agency)
        if not new_items:
            break
        extracted_items += new_items
        page_num += 1
    return extracted_items


def paginate_post_then_follow(session, soup, elements, url, agency):
    extracted_items = []
    for page in soup.select(elements[const.PAGE_CLASS]):
        href = page.attrs.get(const.HREF, "")
        page_url = urljoin(url, href) if (href.startswith("/") or href.startswith("?")) else href
        response = get_page(page_url, session=session)
        page_soup = get_content_for_parser(response.content)
        extracted_items += get_items(page_soup, elements, agency)
    return extracted_items


def paginate_follow_next(soup, elements, url, agency, session=None):
    if not elements.get(const.PAGE_CLASS):
        return []
    extracted_items = []
    visited_urls = set()
    while True:
        next_links = soup.select(elements[const.PAGE_CLASS])
        if not next_links:
            break
        href = next_links[0].attrs.get(const.HREF, "")
        if not href or href in ("#", "javascript:void(0)"):
            break
        page_url = urljoin(url, href) if (href.startswith('/') or href.startswith('?')) else href
        if page_url in visited_urls:
            break
        visited_urls.add(page_url)
        response = get_page(page_url, session=session)
        soup = get_content_for_parser(response.content)
        extracted_items += get_items(soup, elements, agency)
    return extracted_items


def paginate_follow_all(soup, elements, url, agency, session=None):
    if not elements.get(const.PAGE_CLASS):
        return []
    extracted_items = []
    total_pages = soup.select(elements[const.PAGE_CLASS])
    for page in total_pages:
        href = page.attrs[const.HREF]
        page_match = re.search(r'[?&]paged?=(\d+)', href)
        if page_match and re.search(r'[?&]paged?=\d+', url):
            page_url = re.sub(r'(?<=[?&])(paged?=)\d+', f'\\g<1>{page_match.group(1)}', url)
        elif href.startswith('?') or (href.startswith('/') and not href.startswith('//')):
            page_url = urljoin(url, href)
        else:
            page_url = href
        response = get_page(page_url, session=session)
        soup = get_content_for_parser(response.content)
        extracted_items += get_items(soup, elements, agency)
    return extracted_items


def get_items(soup, elements, agency):
    extract = []

    if elements.get(const.LIST_BOX_TAG):
        items = soup.find_all(elements[const.LIST_BOX_TAG])
    else:
        items = soup.find_all(class_=elements[const.LIST_BOX])

    for item in items:
        property_data = extract_property_data(item, elements, agency)
        if property_data:
            extract.append(property_data)

    return extract


def extract_property_data(item, elements, agency):
    address = extract_address(item, elements)
    price = model.parse_price(extract_price(item, elements))
    image = extract_image(item, elements)
    link = extract_property_link(item, elements)

    if not all([address, price, image, link]):
        return None

    return model.PropertyModel(
        date_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        agency=agency,
        address=address,
        price=price,
        old_price=0,
        image_url=image,
        house_url=link,
        active=True,
    )


def extract_address(item, elements):
    address_element = ""

    if elements[const.ADDRESS]:
        addr_container = item.find(class_=elements[const.ADDRESS])
        if addr_container:
            if elements[const.ADDRESS_ELEMENT]:
                addr_tag = addr_container.find(elements[const.ADDRESS_ELEMENT])
                if addr_tag:
                    address_element = addr_tag.text.strip()
            else:
                address_element = addr_container.text.strip()
    else:
        addr_tag = item.find(elements[const.ADDRESS_ELEMENT])
        if addr_tag:
            address_element = addr_tag.text.strip()

    return address_element


def extract_price(item, elements):
    price_elements = item.find_all(class_=elements[const.PRICE])
    if not price_elements:
        return ""

    raw_price = item.find(class_=elements[const.PRICE]).text.strip().replace("£", "")

    if elements.get(const.PRICE_REGEX):
        match = re.search(elements[const.PRICE_REGEX], raw_price)
        return match.group(0) if match else raw_price

    return raw_price


def extract_image(item, elements):
    image_element = ""

    if elements.get(const.IMAGE_SELECT):
        img_tag = item.select_one(elements[const.IMAGE_SELECT])
        if img_tag and elements[const.IMAGE_ATTRS] in img_tag.attrs:
            image_element = img_tag.attrs[elements[const.IMAGE_ATTRS]]
    elif elements[const.IMAGE_URL]:
        image_containers = item.find_all(class_=elements[const.IMAGE_URL])
        if image_containers:
            img_tag = item.find(class_=elements[const.IMAGE_URL]).find(elements[const.IMAGE_ELEMENT])
            if img_tag and elements[const.IMAGE_ATTRS] in img_tag.attrs:
                image_element = img_tag.attrs[elements[const.IMAGE_ATTRS]]

    if image_element and not url_starts_with_https(image_element):
        image_element = urljoin(elements[const.DOMAIN_URL], image_element)

    return image_element


def extract_property_link(item, elements):
    link_elements = item.find_all(elements[const.HOUSE_ELEMENT])
    property_link = ""

    if not link_elements:
        parent = item.parent
        if parent and parent.name == elements.get(const.HOUSE_ELEMENT) and elements.get(const.HOUSE_ATTRS) in parent.attrs:
            property_link = parent.attrs[elements[const.HOUSE_ATTRS]]

    link_tag = item.find(elements[const.HOUSE_ELEMENT])
    if link_tag and elements[const.HOUSE_ATTRS] in link_tag.attrs:
        property_link = link_tag.attrs[elements[const.HOUSE_ATTRS]]

    if property_link and not url_starts_with_https(property_link):
        property_link = urljoin(elements[const.DOMAIN_URL], property_link)

    return property_link


def web_request_successful(response):
    return response.status_code == 200


def get_content_for_parser(content):
    return BeautifulSoup(content, "html.parser")

def url_starts_with_https(url):
    return url.startswith("https://")
