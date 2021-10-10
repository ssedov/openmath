import datetime
import json
import logging
import os

import bson.errors
from bson import ObjectId
from flask import Flask, make_response, request, g, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)

# app.static_folder = './deploy/js/static'
# app.debug = True
cors = CORS(app, resources={
    r"/api/*": {"origins": ['http://localhost:8080', 'http://test.humahisation.ru', 'http://localhost:3000']}, })


def default_response_from_dict(data: dict, code: int = 200, content_type: str = 'application/json'):
    resp = make_response()
    resp.content_type = content_type
    resp.code = code
    resp.data = json.dumps(data)
    return resp


@app.route('/api/')
def hello_world():  # put application's code here
    return 'Hello World!'


@app.route('/api/test/<test_id>')
def render_test(test_id):
    logging.info('Loading test %s', test_id)
    db = mongo()['openmath']
    test = db['tests'].find_one({'test_id': test_id}, {'_id': 0, 'submissions': 0})
    if not test:
        logging.info('not found')
        return default_response_from_dict(data={'status': 'not found'}, code=404)

    questions = []

    fields = {k: 1 for k in ['text', 'question_id', 'answers', 'type']}

    for qid in test['questions']:
        questions.append(db['questions'].find_one({'_id': qid}, fields))
    test['questions'] = questions
    return default_response_from_dict(data=test)


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


@app.route('/')

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


@app.route('/api/question/<string:qid>', methods=['GET'])
def get_question(qid):
    try:
        oid = ObjectId(qid)
        res = mongo()['openmath']['questions'].find_one({'_id': oid})
    except bson.errors.InvalidId:
        res = mongo()['openmath']['questions'].find_one({'question_id': qid})
    res['_id'] = str(res['_id'])
    return default_response_from_dict(res)


@app.route('/api/sumbission/<string:sid>')
def fetch_submission(sid):
    return default_response_from_dict(mongo()['openmath']['submissions'].find_one({'_id': ObjectId(sid)}, {'_id': 0}))


def process_submission(submission):
    files = []
    for f in submission.get('files', []):
        files.append(str(f))
    submission['files'] = files
    submission['ts'] = submission['ts'].strftime('%d.%m.%Y %H:%M:%S')
    return submission


@app.route('/api/submissions/<string:tid>')
def fetch_submissions_by_test(tid):
    cursor = mongo()['openmath']['submissions'].find({'test_id': tid}, {'_id': 0})
    submissions = [s for s in cursor]
    submissions.sort(key=lambda x: x.get('ts'))
    submissions = [process_submission(s) for s in submissions]
    resp = make_response()
    resp.content_type = 'application/json'
    resp.data = json.dumps({'submissions': submissions})
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
