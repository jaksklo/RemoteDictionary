FROM library/python:3.10-slim

WORKDIR /app
COPY dependencies/requirements.txt src/config.py src/rpc_server.py src/server_main.py ./

RUN pip install -r requirements.txt

CMD ["python3", "server_main.py"]
