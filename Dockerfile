FROM python:3.9

RUN pip install flask flask-cors pyyaml pymongo

COPY app.py /app/

CMD python3 /app/app.py