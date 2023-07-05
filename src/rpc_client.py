import asyncio
import uuid
from typing import MutableMapping
from aio_pika import Message, connect_robust
from aio_pika.abc import (
    AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue,
)
import json
from config import Settings
from tenacity import retry, stop_after_attempt, wait_fixed
from loguru import logger


class RemoteDictRpcClient:
    connection: AbstractConnection
    channel: AbstractChannel
    callback_queue: AbstractQueue
    loop: asyncio.AbstractEventLoop

    def __init__(self) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}
        self.loop = asyncio.get_running_loop()
        self.settings = Settings()

    # retry connection setup in case broker is not ready yet
    @retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
    async def connect(self) -> "RemoteDictRpcClient":
        """Method for establishing connection with RabbitMQ"""
        # create connection to RabbitMQ
        try:
            self.connection = await connect_robust(
                host=self.settings.RABBITMQ_HOST,
                port=self.settings.RABBITMQ_PORT,
                login=self.settings.RABBITMQ_LOGIN,
                password=self.settings.RABBITMQ_PASSWORD,
                ssl=self.settings.RABBITMQ_SSL)

            self.channel = await self.connection.channel()
            self.callback_queue = await self.channel.declare_queue(self.settings.RABBITMQ_RESULT_QUEUE, auto_delete=True)
            # declare a queue
            await self.channel.declare_queue(self.settings.RABBITMQ_TASK_QUEUE)
            await self.callback_queue.consume(self.on_response, timeout=3)
            logger.info("Rabbit connection established successfully.")
            return self
        except ConnectionError:
            logger.warning("Rabbit broker not available, retrying connection in 10 seconds...")
            raise Exception

    async def disconnect(self) -> None:
        """Method for closing broker connection on shutdown"""
        await self.connection.close()

    def on_response(self, message: AbstractIncomingMessage) -> None:
        """Define action to trigger on response from broker"""
        if message.correlation_id is None:
            logger.error("Message correlation id is missing.")
            return
        future: asyncio.Future = self.futures.pop(message.correlation_id)
        future.set_result(message.body)

    async def call(self, message: dict) -> dict:
        """Send request to remote server with broker connection"""
        correlation_id = str(uuid.uuid4())
        future = self.loop.create_future()
        self.futures[correlation_id] = future
        await self.channel.default_exchange.publish(
            Message(
                body=json.dumps(message).encode(),
                content_type="text/plain",
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name,
            ),
            routing_key=self.settings.RABBITMQ_TASK_QUEUE,
        )
        return await future



