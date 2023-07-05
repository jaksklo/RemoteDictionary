from loguru import logger
from aiohttp import web
import asyncio
from rpc_server import RemoteDictRpcServer
import sys
logger.remove()
logger.add(sys.stdout, format="{time:HH:mm:ss} - {level} - {message}", level="INFO")


async def background_task(_app) -> None:
    # startup stage
    logger.info("Application startup...")
    server = await RemoteDictRpcServer().setup()
    _app['rpc_server'] = server

    # main background task
    task = asyncio.create_task(_app['rpc_server'].process_tasks())
    yield

    # shutdown stage
    logger.info("Gracefully shutting server app down.")
    await _app['rpc_server'].disconnect()
    task.cancel()


if __name__ == "__main__":
    app = web.Application()
    app.cleanup_ctx.append(background_task)
    web.run_app(app)
