import json
import re

with open("token_index.json", 'r', encoding='utf-8') as f:
    token_index = json.load(f)

with open("url_index.json", 'r', encoding='utf-8') as f:
    url_index = json.load(f)

with open("pagerank.json", 'r', encoding='utf-8') as f:
    pagerank = json.load(f)

def and_postings(a, b):
    i, j = 0, 0
    result = []
    while i < len(a) and j < len(b):
        if a[i][0] < b[j][0]:
            i += 1
        elif a[i][0] > b[j][0]:
            j += 1
        else:
            result.append((a[i][0], (a[i][1] + b[j][1]) / 2.0))
            i += 1
            j += 1
    return result

def get_token_id(token):
    if token not in token_index:
        return None
    else:
        return token_index[token]

from nltk.stem import PorterStemmer
stemmer = PorterStemmer()

def tokenize_and_stem(text):
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    return [stemmer.stem(tok) for tok in tokens]

token_chunk_size = 10000

def get_token_url_ids(tid):
    chunk = str(tid % token_chunk_size)
    filename = "final_index/final_chunk" + str(chunk) + ".json"
    with open(filename, 'r', encoding='utf-8') as f:
        partial_index = json.load(f)
    return partial_index[str(tid)]

def get_results(query):
    tokens = tokenize_and_stem(query)
    url_ids = None

    for token in tokens:
        token_id = get_token_id(token)
        if token_id == None:
            url_ids = []
            continue
        token_url_ids = get_token_url_ids(token_id)
        url_ids = and_postings(url_ids, token_url_ids) if url_ids is not None else token_url_ids

    alpha = 1000.0
    # Huge alpha because the pagerank values are so small
    url_ids = [(doc_id, tfidf * (1 + alpha * pagerank[str(doc_id)]))
               for doc_id, tfidf in url_ids]

    # Sort by final combined score descending
    url_ids.sort(key=lambda x: x[1], reverse=True)

    urls = [url_index[str(doc_id)] for doc_id, _ in url_ids]

    if urls == []:
        return 'NO RESULTS', 0
    else:
        return urls[:5], len(urls)

if __name__ == '__main__':
    while (True):
        print('Enter search query:')
        query = input()
        if query == 'QUIT':
            break
        results, cnt = get_results(query)
        for result in results:
            print(result)

