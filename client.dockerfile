FROM library/python:3.10-slim

WORKDIR /app
COPY dependencies/requirements.txt  src/config.py src/rpc_client.py src/client_main.py ./

RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["python3", "client_main.py"]
