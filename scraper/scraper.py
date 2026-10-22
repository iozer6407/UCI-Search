import re
from urllib.parse import urlparse, urlunparse, urldefrag, parse_qs, urljoin
from bs4 import BeautifulSoup
import json
import os
from collections import Counter

FREQS_FILE = "word_freqs.json"
SAVE_INTERVAL = 50

global_word_freq = Counter()
processed_count = 0

max_word_count_url = None

max_word_count_value = 0

previous = set()

def load_global_freqs():
    global global_word_freq
    if os.path.exists(FREQS_FILE):
        with open(FREQS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            global_word_freq.update(data)


def save_global_freqs():
    with open(FREQS_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(global_word_freq), f, indent=2)
    print(f"[+] Saved global word frequencies ({sum(global_word_freq.values())} total words)")

def extract_words_from_html(content):
    soup = BeautifulSoup(content, "html.parser")

    # remove scripts and styles
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    text = soup.get_text(separator=" ").lower()
    return re.findall(r"\b[a-z0-9]+\b", text)


def scraper(url, resp):
    global global_word_freq, processed_count
    global max_word_count_url, max_word_count_value

    if resp.status == 200 and resp.raw_response is not None:
        try:
            content = resp.raw_response.content
            words = extract_words_from_html(content)
            global_word_freq.update(words)
            processed_count += 1

            # --- NEW: track page with most words ---
            word_count = len(words)
            if word_count > max_word_count_value:
                max_word_count_value = word_count
                max_word_count_url = url
                print(f"[New max words: {word_count}] {url}")

            if processed_count % SAVE_INTERVAL == 0:
                save_global_freqs()

        except Exception as e:
            print(f"[!] Failed to extract words from {url}: {e}")

    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def is_trap_page(content):
    # Avoid empty or huge pages with little text
    if not content:
        return True
    
    # Heuristic limit for size
    max_size = 5 * 1024 * 1024   # 5 MB
    min_text_ratio = 0.02         # at least 2% of content should be text

    if len(content) > max_size:
        return True

    soup = BeautifulSoup(content, "html.parser")
    text = soup.get_text(separator=' ', strip=True)
    text_ratio = len(text) / max(1, len(content))

    return text_ratio < min_text_ratio

def looks_like_login_page(content):
    try:
        soup = BeautifulSoup(content, "html.parser")

        # Find forms that look like authentication
        forms = soup.find_all("form")
        for form in forms:
            # Check for input fields commonly used in login pages
            inputs = [inp.get("name", "").lower() for inp in form.find_all("input")]
            if any("user" in i or "email" in i for i in inputs) and any("pass" in i for i in inputs):
                return True
            if "login" in form.get("action", "").lower():
                return True
        return False
    except Exception:
        return False

def extract_next_links(url, resp):
    # Only process successful responses
    if resp.status != 200 or resp.raw_response is None:
        return []
    
    content = resp.raw_response.content

    # Skip trap-like or login-like pages
    if is_trap_page(content):
        return []
    
    if looks_like_login_page(content):
        return []

    # Parse HTML
    soup = BeautifulSoup(content, "html.parser")
    links = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        absolute_url = urljoin(url, href)

        # Remove fragments (#...) and query strings (?...)
        # At first I wanted to keep this, but it was just too much
        absolute_url, _ = urldefrag(absolute_url)
        parsed = urlparse(absolute_url)
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

        links.append(clean_url)

    return links


def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        
        domain = parsed.hostname.lower() if parsed.hostname else ""
        if not (
            domain.endswith(".ics.uci.edu")
            or domain.endswith(".cs.uci.edu")
            or domain.endswith(".informatics.uci.edu")
            or domain.endswith(".stat.uci.edu")
        ):
            return False

        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False

        login_keywords = {
            "login", "signin", "sign-in", "sign_in",
            "logout", "signout", "auth", "account",
            "register", "signup", "sign-up", "user", "password"
        }

        path = parsed.path.lower()
        query = parsed.query.lower()
        query_params = " ".join(parse_qs(query).keys())

        # This guy has like billions of urls
        if path.startswith("/~eppstein/pub") or path.startswith("/~eppstein/pix"):
            return False

        if any(k in path for k in login_keywords) or any(k in query for k in login_keywords) or any(k in query_params for k in login_keywords):
            return False

        normalized_url = parsed.geturl().lower().strip()
        if normalized_url in previous:
            return False
        previous.add(normalized_url)

        return True

    except TypeError:
        print ("TypeError for ", parsed)
        raise