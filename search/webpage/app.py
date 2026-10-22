# app.py
from flask import Flask, render_template, request, jsonify

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from search import get_results

app = Flask(__name__)

# --- Route to Serve the HTML Page ---
@app.route('/')
def index():
    # Flask looks for index.html inside a folder named 'templates'
    return render_template('index.html')

import time

# --- Route to Handle the Search Request ---
@app.route('/api/process_text', methods=['POST'])
def process_text():
    data = request.get_json()
    text = data.get('text', '')

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    start = time.time()
    results, cnt = get_results(text)
    end = time.time()
    elapsed_ms = round((end - start) * 1000, 2)

    return jsonify({
        'search': text,
        'results': results,
        'result_count': cnt,
        'elapsed_time_ms': elapsed_ms
    })

if __name__ == '__main__':
    app.run(debug=True)


    import time
