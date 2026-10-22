import json
import os
import re
import math
from bs4 import BeautifulSoup
from collections import Counter
import hashlib

from bs4 import XMLParsedAsHTMLWarning
from bs4 import MarkupResemblesLocatorWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

from nltk.stem import PorterStemmer

stemmer = PorterStemmer()

def tokenize_and_stem(text):
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    return [stemmer.stem(tok) for tok in tokens]

from urllib.parse import urljoin, urlparse, urlunparse

def remove_fragment(url):
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)

def normalize_url(base_url, link):
    if not link:
        return None
    try:
        absolute = urljoin(base_url, link)
        url = remove_fragment(absolute)
    except:
        return link
    return url

def extract_data_from_html(html_content, url):
    if not html_content:
        return {
            "important": set(),
            "normal": Counter(),
            "anchors": []
        }

    soup = BeautifulSoup(html_content, "html5lib")

    important_tokens = set()
    normal_tokens = Counter()

    def add_tokens(text, mark_important=False):
        toks = tokenize_and_stem(text)
        for t in toks:
            normal_tokens[t] += 1
            if mark_important:
                important_tokens.add(t)

    if soup.title:
        add_tokens(soup.title.get_text(" ", strip=True), mark_important=True)

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        add_tokens(tag.get_text(" ", strip=True), mark_important=True)

    for tag in soup.find_all(["b", "strong"]):
        add_tokens(tag.get_text(" ", strip=True), mark_important=True)

    anchors = []
    for a in soup.find_all("a"):
        href = normalize_url(url, a.get("href", None))
        anchor_text = a.get_text(" ", strip=True)

        anchor_tokens = tokenize_and_stem(anchor_text)
        for t in anchor_tokens:
            normal_tokens[t] += 1

        if href:
            anchors.append((href, anchor_tokens))

    full_text = soup.get_text(" ", strip=True)
    for t in tokenize_and_stem(full_text):
        normal_tokens[t] += 1

    return {
        "important": important_tokens,
        "normal": normal_tokens,
        "anchors": anchors
    }

def collect_all_json_paths():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "data")

    paths = []

    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.lower().endswith(".json"):
                paths.append(os.path.join(root, file))

    return paths

def read_json_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return None

def save_file(index, filename, pretty = True):
    with open(filename, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(index, f, ensure_ascii=False, indent=2)
        else:
            json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    
    print(f"Saved {filename}")

url_index = {}
index_url = {}
token_index = {}
token_cnt = {} # How many documents contain this token

def index_file(data, doc_id, index):
    f, i = dict(), dict()
    for tok, freq in data['normal'].items():
        f[tok] = freq
        i[tok] = 0

    for tok in data['important']:
        i[tok] = 1

    for tok, freq in f.items():
        tok_idx = token_index[tok]
        if tok_idx not in index:
            index[tok_idx] = []
        index[tok_idx].append((doc_id, freq, i[tok]))

token_chunk_size = 10000
partial_chunk_size = 100

if __name__ == "__main__":
    paths = collect_all_json_paths()
    paths.sort()

    # Create all of the partial indexes
    doc_id = 0
    tok_id = 0
    partial_index = {}
    partial_index_cnt = 0

    # To remove exact duplicates
    content_hashes = set()

    connections = {}
    for path in paths:
        data = read_json_file(path)
        html_data = extract_data_from_html(data['content'], data['url'])

        # Skip duplicate documents
        url = remove_fragment(data['url'])
        if url in index_url:
            continue

        try:
            soup_for_hash = BeautifulSoup(data['content'], "html5lib")
            text_for_hash = soup_for_hash.get_text(" ", strip=True)
        except:
            text_for_hash = data['content']

        doc_hash = hashlib.md5(text_for_hash.encode("utf-8")).hexdigest()

        if doc_hash in content_hashes:
            continue
        content_hashes.add(doc_hash)

        # Add tokens to index
        for tok, freq in html_data['normal'].items():
            if tok not in token_index:
                token_index[tok] = tok_id
                token_cnt[tok_id] = 1
                tok_id += 1
            else:
                token_cnt[token_index[tok]] += 1

        connections[doc_id] = html_data['anchors']

        # Add document to index
        index_file(html_data, doc_id, partial_index)
        url_index[doc_id] = url
        index_url[url] = doc_id
        doc_id += 1

        if doc_id % partial_chunk_size == 0:
            save_file(partial_index, "partial_index/partial_index" + str(partial_index_cnt) + ".json", False)
            partial_index = {}
            partial_index_cnt += 1
    if doc_id % partial_chunk_size != 0:
        save_file(partial_index, "partial_index/partial_index" + str(partial_index_cnt) + ".json", False)
        partial_index = {}
        partial_index_cnt += 1


    # Anchor index is way more sparse, does not need to be stored away
    graph = {}
    anchor_freqs = {}
    anchor_index = {}

    for id in range(doc_id):
        graph[id] = set()

    # Create graph, and collect anchor tokens
    for source, targets in connections.items():
        for target, tokens in targets:
            if target not in index_url:
                continue
            target_id = index_url[target]
            graph[source].add(target_id)
            if target_id not in anchor_freqs:
                anchor_freqs[target_id] = {}
            for tok in tokens:
                tok_idx = token_index[tok]
                if tok_idx not in anchor_freqs[target_id]:
                    anchor_freqs[target_id][tok_idx] = 0
                anchor_freqs[target_id][tok_idx] += 1
    
    # Create postings for anchor tokens
    for target, tokens in anchor_freqs.items():
        for tok, freq in tokens.items():
            tok_idx = tok
            if tok_idx not in anchor_index:
                anchor_index[tok_idx] = []
            anchor_index[tok_idx].append((target, freq, 1))
        anchor_index

    def pagerank(graph, damping=0.85, max_iter=100, delta=1e-6):
        N = len(graph)
        if N == 0:
            return {}

        # Initialize rank uniformly
        rank = {node: 1.0 / N for node in graph}

        for it in range(max_iter):
            new_rank = {node: (1 - damping) / N for node in graph}  # teleportation

            # Sum of ranks for dangling nodes
            dangling_sum = sum(rank[node] for node, out_links in graph.items() if not out_links)

            # Distribute rank from normal nodes
            for node, out_links in graph.items():
                if out_links:
                    share = damping * rank[node] / len(out_links)
                    for target in out_links:
                        new_rank[target] += share

            # Distribute dangling node rank equally
            dangling_share = damping * dangling_sum / N
            for node in graph:
                new_rank[node] += dangling_share

            # Convergence check
            diff = sum(abs(new_rank[n] - rank[n]) for n in graph)
            rank = new_rank
            if diff < delta:
                break

        return rank

    pagerank_values = pagerank(graph)

    save_file(pagerank_values, "pagerank.json")
    save_file(url_index, "url_index.json")
    save_file(token_index, "token_index.json")
    save_file(token_cnt, "token_cnt.json")

    save_file(anchor_index, "partial_index/anchor_index.json")

    anchor_buckets = [dict() for _ in range(token_chunk_size)]

    for tok, postings in anchor_index.items():
        bucket = tok % token_chunk_size
        anchor_buckets[bucket][tok] = postings

    N = len(token_index)
    K = len(url_index)

    def tf_idf(tok, freq, imp):
        return (1 + math.log(freq)) * (math.log(K / token_cnt[tok]) + 1) * (2 if imp else 1)
    
    for fi in range(token_chunk_size):
        final_chunk = {}

        # Add normal text postings
        for pi in range(partial_index_cnt):
            partial_index = read_json_file(f"partial_index/partial_index{pi}.json")
            for tok_str, postings in partial_index.items():
                tok = int(tok_str)
                if tok % token_chunk_size != fi:
                    continue
                
                if tok not in final_chunk:
                    final_chunk[tok] = {}

                for doc_id, freq, imp in postings:
                    weight = tf_idf(tok, freq, imp)
                    final_chunk[tok][doc_id] = weight

        # Merge anchor text postings
        for tok, postings in anchor_buckets[fi].items():
            if tok not in final_chunk:
                final_chunk[tok] = {}

            for doc_id, freq, imp in postings:
                weight = tf_idf(tok, freq, imp)
                if doc_id in final_chunk[tok]:
                    final_chunk[tok][doc_id] += weight
                else:
                    final_chunk[tok][doc_id] = weight

        # Convert inner dict to list for saving
        for tok in final_chunk:
            final_chunk[tok] = sorted(
                [(doc_id, w) for doc_id, w in final_chunk[tok].items()],
                key=lambda x: x[0]  # sort by doc_id
            )
        # Save final chunk
        save_file(final_chunk, "final_index/final_chunk" + str(fi) + ".json", pretty=False)