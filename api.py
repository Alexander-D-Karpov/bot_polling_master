#!/usr/bin/env python
# encoding: utf-8
import json
from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route('/', methods=['GET'])
def query_records():
    name = request.args.get('name')
    print(name)
    with open('/tmp/data.txt', 'r') as f:
        data = f.read()
        records = json.loads(data)
        for record in records:
            if record['name'] == name:
                return jsonify(record)
        return jsonify({'error': 'data not found'})


@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    record = json.loads(request.data)
    id = record["id"]
    print(id)


@app.route('/start_bot', methods=['POST'])
def update_record():
    record = json.loads(request.data)
    token = record["token"]
    print(token)


app.run(debug=True)