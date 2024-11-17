from flask import Flask, request, render_template, jsonify
import argparse
import os
import cv2
import numpy as np
import base64
from image_matcher import ImageMatcher
from collections import Counter

app = Flask(__name__)

image_matcher = None
ABSOLUTE_PATH = None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload_image', methods=['POST'])
def upload_image():
    global image_matcher, ABSOLUTE_PATH

    data = request.json.get('image')
    n = int(request.json.get('n', 1))

    if not data:
        return jsonify({'error': 'No image data received'}), 400

    # Decode the base64 image
    header, encoded = data.split(',', 1)
    image_data = base64.b64decode(encoded)
    np_arr = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None:
        return jsonify({'error': 'Invalid image data'}), 400

    # Get top N matches
    matches = image_matcher.match_image_top_n(image, n)

    if not matches:
        return jsonify({'error': 'No matches found'}), 200

    response_data = []

    for match in matches:
        filename = match['filename']
        full_path = 'http://localhost:8000/' + match['slugcat'] + '/' + match['region'] + '/' + filename
        response_data.append({
            'slugcat': match['slugcat'],
            'region': match['region'],
            'filename': filename,
            'room_key': match['room_key'],
            'distance': match['distance'],
            'image_path': full_path
        })

    return jsonify({'matches': response_data}), 200

@app.route('/get_base_path', methods=['GET'])
def get_base_path():
    global ABSOLUTE_PATH
    return jsonify({'base_path': ABSOLUTE_PATH})

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run the Flask image matcher server.')
    parser.add_argument('base_dir', help='Base directory containing images.')
    parser.add_argument('--search_filter',
                        help='Comma-separated list of slugcat/region pairs or slugcat names to filter the search.')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the server.')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server.')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguments()
    ABSOLUTE_PATH = os.path.abspath(args.base_dir)
    image_matcher = ImageMatcher(ABSOLUTE_PATH, search_filter=args.search_filter or None)
    app.run(host=args.host, port=args.port)
