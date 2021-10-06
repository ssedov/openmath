import datetime
import json
import logging
import os
from logging.config import dictConfig

from flask import Flask, make_response, request, g
from flask_cors import CORS, cross_origin
from pymongo import MongoClient

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__)
cors = CORS(app, resources={
    r"/api/*": {"origins": ['http://localhost:8080', 'http://test.humahisation.ru', 'http://localhost:3000']}, })


@app.route('/api/')
def hello_world():  # put application's code here
    return 'Hello World!'


@app.route('/api/test/<test_id>')
def render_test(test_id):
    logging.info('Loading test %s', test_id)
    resp = make_response()
    db = mongo()['openmath']
    test = db['tests'].find_one({'test_id': test_id}, {'_id': 0, 'submissions': 0})
    if not test:
        logging.info('not found')
        resp.data = json.dumps({'status': 'not_found'})
        resp.status_code = 404
        return resp

    questions = []
    for qid in test['questions']:
        questions.append(db['questions'].find_one({'_id': qid}, {'_id': 0}))
    test['questions'] = questions

    resp.data = json.dumps(test)
    resp.content_type = 'application/json'

    return resp


@app.route('/api/submit/<test_id>', methods=['POST'])
@cross_origin()
def opts(test_id):
    resp = make_response()
    resp.location = '/success.htm'
    logging.info(request.headers)
    logging.info(request.json)
    data = request.json
    data['ts'] = datetime.datetime.now()
    data['test_id'] = test_id
    sub = mongo()['openmath']['submissions'].insert_one(data)
    resp.data = json.dumps({'status': 'success', 'submission_id': str(sub.inserted_id)})
    mongo()['openmath']['tests'].find_one_and_update({'test_id': test_id}, {'$push': {'submissions': sub.inserted_id}})
    resp.status_code = 200
    return resp


def mongo():
    if 'mongo' in g:
        return g.mongo
    user = os.environ.get('MONGO_USER', 'root')
    password = os.environ.get('MONGO_PASS', 'example')
    mongo_host = os.environ.get('MONGO_HOST', 'mongo')
    g.mongo = MongoClient(f'mongodb://{user}:{password}@{mongo_host}:27017')
    return g.mongo


if __name__ == '__main__':
    app.run(host='0.0.0.0')
