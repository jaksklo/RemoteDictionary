import asyncio
import json
from aiohttp import web
from rpc_client import RemoteDictRpcClient
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, format="{time:HH:mm:ss} - {level} - {message}", level="INFO")

routes = web.RouteTableDef()


@routes.get('/get_value')
async def get_from_remote_dict(request):
    # make sure 'key' parameter exists
    try:
        key = request.query['key']
        message = {"command": "get", 'key': key}
    except KeyError as ke:
        msg = "Missing query parameter: {}".format(ke)
        response = {"error": msg}
        logger.error(msg)
        return web.json_response(response)

    # use existing rabbit connection
    rpc_client = request.app['rpc_client']

    # send get task to remote server via rabbit and wait for response no longer than 2 secs
    try:
        response = await asyncio.wait_for(rpc_client.call(message), timeout=2.0)
        return web.json_response(json.loads(response))
    except asyncio.TimeoutError:
        msg = "Timeout on waiting for server response"
        response = {"error": msg}
        logger.error(msg)
        return web.json_response(response)
    except Exception as e:
        msg = "An error occurred during request processing"
        response = {"error": msg}
        logger.error(e)
        return web.json_response(response)


@routes.post("/set_value")
async def set_to_remote_dict(request):
    # make sure 'key' and 'value' params are passed, validate value - only floats accepted
    try:
        key = request.query['key']
        value = float(request.query['value'])
        message = {"command": "set", 'key': key, 'value': value}
    except KeyError as ke:
        response = {"error": "Missing query parameter: {}".format(ke)}
        return web.json_response(response)

    except ValueError as e:
        response = {"error": "Incorrect type of value parameter: {}".format(e)}
        return web.json_response(response)

    # use existing rabbit connection
    rpc_client = request.app['rpc_client']

    # send set task to remote server via rabbit and wait for response no longer than 2 secs
    try:
        response = await asyncio.wait_for(rpc_client.call(message), timeout=2.0)
        return web.json_response(json.loads(response))
    except asyncio.TimeoutError:
        msg = "Timeout on waiting for server response"
        response = {"error": msg}
        logger.error(msg)
        return web.json_response(response)
    except Exception as e:
        msg = "An error occurred during request processing"
        response = {"error": msg}
        logger.error(e)
        return web.json_response(response)


async def on_startup(_app):
    logger.info("Application startup...")
    client = await RemoteDictRpcClient().connect()
    _app['rpc_client'] = client


async def on_shutdown(_app):
    logger.info("Gracefully shutting client app down")
    await _app['rpc_client'].disconnect()


if __name__ == "__main__":
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.add_routes(routes)
    web.run_app(app, port=8080)
