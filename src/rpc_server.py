from tenacity import retry, stop_after_attempt, wait_fixed
from aio_pika import Message, connect_robust
from aio_pika.abc import AbstractIncomingMessage
import json
import aiosqlite
from config import Settings
from loguru import logger


class RemoteDictRpcServer:
    def __init__(self):
        self.channel = None
        self.exchange = None
        self.queue = None
        self.connection = None
        self.settings = Settings()

    # retry connection setup in case broker is not ready yet
    @retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
    async def setup(self) -> "RemoteDictRpcServer":
        """Method for establishing connection with RabbitMQ and SQLite db setup"""
        # create connection to RabbitMQ
        try:
            self.connection = await connect_robust(
                host=self.settings.RABBITMQ_HOST,
                port=self.settings.RABBITMQ_PORT,
                login=self.settings.RABBITMQ_LOGIN,
                password=self.settings.RABBITMQ_PASSWORD,
                ssl=self.settings.RABBITMQ_SSL)
            logger.info("Rabbit connection established successfully.")
        except ConnectionError:
            logger.warning("Rabbit broker not available, retrying connection in 10 seconds...")
            raise Exception

        # establish a channel
        self.channel = await self.connection.channel()
        self.exchange = self.channel.default_exchange

        # declare a queue
        self.queue = await self.channel.declare_queue(self.settings.RABBITMQ_TASK_QUEUE)

        # initialize sqlite database if does not exist
        async with aiosqlite.connect("/data/" + self.settings.SQLITEDB_FILE) as db:
            sql = "create table if not exists {} (key text unique , value float);".format(self.settings.SQLITEDB_TABLE)
            await db.execute(sql)
            await db.commit()

        logger.info("Remote dictionary server setup completed.")
        return self

    async def disconnect(self) -> None:
        """Method for closing broker connection on shutdown"""
        await self.connection.close()

    async def process_tasks(self) -> None:
        """Method for asynchronous Rabbit message consumption and processing."""
        async with self.queue.iterator() as q:
            message: AbstractIncomingMessage
            async for message in q:
                try:
                    async with message.process(requeue=False):
                        assert message.reply_to is not None
                        data = json.loads(message.body)
                        resp_msg = await self._interact_with_db(data)
                        response = json.dumps(resp_msg).encode()
                        await self.exchange.publish(
                            Message(body=response, correlation_id=message.correlation_id),
                            routing_key=message.reply_to)
                except Exception as e:
                    logger.exception("Processing error for message {} ({})".format(message, e))

    async def _interact_with_db(self, data) -> dict:
        """Method for fetching or inserting key-value pair to table in db"""
        try:
            async with aiosqlite.connect("/data/" + self.settings.SQLITEDB_FILE) as db:
                # task type 1 : retrieve from database
                if data['command'] == 'get':
                    sql = "SELECT value FROM {} WHERE key='{}'".format(self.settings.SQLITEDB_TABLE, data['key'])
                    async with db.execute(sql) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            resp_msg = {data['key']: row[0]}
                        else:
                            msg = "Record with key '{}' does not exist".format(data['key'])
                            resp_msg = {"error": msg}
                            logger.error(msg)

                # task type 2 : upsert in database
                elif data['command'] == 'set':
                    sql = "INSERT INTO {} (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value".format(self.settings.SQLITEDB_TABLE)
                    await db.execute(sql, (data['key'], data['value']))
                    await db.commit()
                    resp_msg = {"status": "successfully inserted: {}".format({data['key']: data['value']})}

                # for other commands report error
                else:
                    msg = "wrong command type".format(data['command'])
                    resp_msg = {"error": msg}
                    logger.error(msg)

            return resp_msg
        except Exception as e:
            resp_msg = {"error": "Server side error occurred while processing request"}
            logger.error(e)
            return resp_msg
