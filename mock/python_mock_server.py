from flask import Flask, jsonify, make_response
from pathlib import Path
import json

app = Flask(__name__)


@app.route('/v1_route', methods=['GET'])
def v1_route():
    repo_root = Path(__file__).resolve().parents[1]
    db_path = repo_root / 'mock' / 'db.json'
    try:
        data = json.loads(db_path.read_text())
        # json-server returns the object directly for /v1_route, so keep same shape
        resp = make_response(jsonify(data.get('v1_route', {})))
        # Allow dev frontend (vite) to fetch this mock
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        resp = make_response(jsonify({'error': str(e)}), 500)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp


if __name__ == '__main__':
    # Use port 3001 to match json-server default used earlier
    app.run(host='127.0.0.1', port=3001)
