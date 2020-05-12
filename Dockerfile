FROM python:3.6
WORKDIR /abb/
COPY requirements.txt ./
RUN pip install -r requirements.txt
CMD [ "python3", "abb.py" ]