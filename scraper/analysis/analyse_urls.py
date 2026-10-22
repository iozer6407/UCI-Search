import re
from urllib.parse import urlparse
from collections import defaultdict

def extract_url_status_from_file(filename):
    pattern = re.compile(r"Downloaded (http[^\s,]+), status <(\d+)>")
    pairs = []
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                url, status = match.groups()
                pairs.append((url, status))
    return pairs


if __name__ == "__main__":
    filename = "urls.txt"
    pairs = extract_url_status_from_file(filename)

    domain_urls = defaultdict(list)

    for url, status in pairs:
        hostname = urlparse(url).hostname
        if hostname:
            domain_urls[hostname].append(url)

    print("\nDistinct URLs per subdomain")
    for domain in sorted(domain_urls.keys()):
        print(f"{domain}: {len(domain_urls[domain])}")
