from pydantic import BaseSettings


class Settings(BaseSettings):

    RABBITMQ_HOST: str = '172.19.0.2'
    RABBITMQ_PORT: int = 5672
    RABBITMQ_LOGIN: str = 'user'
    RABBITMQ_PASSWORD: str = 'bitnami'
    RABBITMQ_SSL: bool = False
    RABBITMQ_TASK_QUEUE: str = 'task_queue'
    RABBITMQ_RESULT_QUEUE: str = 'result_queue'


    SQLITEDB_FILE: str = '../data/datastorage1.db'
    SQLITEDB_TABLE: str = 'dictionary'

    class Config:
        env_file = '../configuration/.env'
        env_file_encoding = 'utf-8'
