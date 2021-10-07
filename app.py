import datetime
import json
import logging
import os

from bson import ObjectId
from flask import Flask, make_response, request, g, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient

# dictConfig({
#     'version': 1,
#     'formatters': {'qqq': {
#         'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
#     }},
#     'handlers': {'stderr': {
#         'class': 'logging.StreamHandler',
#         'stream': 'ext://flask.logging.wsgi_errors_stream',
#         # 'stream': 'ext://sys.stdout',
#         'formatter': 'qqq'
#     }},
#     'root': {
#         'level': 'DEBUG',
#         'handlers': ['stderr']
#     }
# })

app = Flask(__name__)

# app.static_folder = './deploy/js/static'
# app.debug = True
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


@app.route('/api/upload', methods=['PUT'])
def upload_file():
    for k in request.files:
        file = request.files[k]
        if file:
            filename = file.filename
            sid = ObjectId(request.headers['SubmissionId'])
            res = mongo()['openmath']['uploads'].insert_one({'name': filename})
            # ToDo: assign to correct question IDs
            mongo()['openmath']['submissions'].find_one_and_update({'_id': sid}, {'$push': {'files': res.inserted_id}})
            upload_dir = os.path.join(os.environ.get('UPLOAD_DIR', './uploads'), str(sid))
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            return {'file_id': str(res.inserted_id)}
    return {}


@app.route('/api/image/<image_id>')
def get_image(image_id):
    img = mongo()['openmath']['images'].find_one({'_id': ObjectId(image_id)}, {'_id': 0})
    resp = make_response()
    if img:
        resp.status_code = 200
        if 'svg' in img:
            resp.content_type = 'image/svg+xml'
            resp.data = img['svg']
            resp.status_code = 200
        else:
            resp.data = ''
            resp.status_code = 500
    else:
        resp.status_code = 404
        resp.data = ''

    return resp


@app.route('/api/submit')
def get_submission_id():
    sub = mongo()['openmath']['submissions'].insert_one({})
    return {'submission_id': str(sub.inserted_id)}


@app.route('/api/submit/<test_id>', methods=['POST'])
def opts(test_id):
    sid = ObjectId(request.headers['SubmissionId'])
    resp = make_response()
    resp.location = '/success.htm'
    logging.info(request.headers)
    logging.info(request.json)
    data = request.json
    data['ts'] = datetime.datetime.now()
    data['test_id'] = test_id
    mongo()['openmath']['submissions'].find_one_and_update({'_id': sid}, {'$set': data})
    resp.data = json.dumps({'status': 'success', 'submission_id': str(sid)})

    mongo()['openmath']['tests'].find_one_and_update({'test_id': test_id}, {'$push': {'submissions': ObjectId(sid)}})
    resp.status_code = 200
    return resp


@app.route('/<path:path>')
def send_js(path='123'):
    return send_from_directory('deploy/js', path)


def mongo():
    if 'mongo' in g:
        return g.mongo
    user = os.environ.get('MONGO_USER', 'root')
    password = os.environ.get('MONGO_PASS', 'example')
    mongo_host = os.environ.get('MONGO_HOST', 'mongo')
    g.mongo = MongoClient(f'mongodb://{user}:{password}@{mongo_host}:27017')
    return g.mongo


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
