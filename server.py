import websockets
import asyncio
import logging
import signal
import aiohttp_cors
from aiohttp import web
from websockets.exceptions import ConnectionClosedError
import sqlite3

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Подключение к базе данных
conn = sqlite3.connect('drones.db')
c = conn.cursor()

# Создание таблицы для дронов, если она еще не существует
c.execute('''
    CREATE TABLE IF NOT EXISTS drones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
''')
conn.commit()


async def get_drones(request):
    """
    Обработка запроса на получение списка дронов.

    :param request: Запрос HTTP.
    :return: JSON-ответ с данными о доступных дронах.
    """
    c.execute('SELECT id, name FROM drones')
    drones = [{"id": row[0], "name": row[1]} for row in c.fetchall()]
    return web.json_response(drones)


async def add_drone(request):
    """
    Обработка запроса на добавление нового дрона.

    :param request: Запрос HTTP.
    """
    data = await request.json()
    name = data.get("name")
    if name:
        c.execute('INSERT INTO drones (name) VALUES (?)', (name,))
        conn.commit()
        return web.Response(text="Дрон добавлен")
    return web.Response(text="Ошибка добавления дрона", status=400)


async def delete_drone(request):
    """
    Обработка запроса на удаление дрона.

    :param request: Запрос HTTP.
    """
    data = await request.json()
    drone_id = data.get("id")
    if drone_id:
        c.execute('DELETE FROM drones WHERE id = ?', (drone_id,))
        conn.commit()
        return web.Response(text="Дрон удален")
    return web.Response(text="Ошибка удаления дрона", status=400)


async def control_drone(websocket):
    """
    Обработка управления дроном через WebSocket.

    :param websocket: WebSocket-соединение клиента.
    """
    client_ip = websocket.remote_address[0]
    client_port = websocket.remote_address[1]
    logging.info(f"Подключен клиент: {client_ip}:{client_port}")

    command = {
        "takeoff": "Квадрокоптер взлетает",
        "land": "Дрон приземляется",
        "hover": "Квадрокоптер завис",
        "move_forward": "Квадрокоптер летит вперед",
        "move_back": "Квадрокоптер летит назад",
        "move_left": "Квадрокоптер летит налево",
        "move_right": "Квадрокоптер летит направо",
        "move_turns_around_left": "Квадрокоптер поворачивается налево",
        "move_turns_around_right": "Квадрокоптер поворачивается направо",
        "start_engines": "Двигатели дрона запущены",
        "return_base": "Квадрокоптер возвращается на базу",
        "сargo_dumping": "Груз сброшен"
    }

    selected_drone = None  # Выбранный дрон

    try:
        async for msg in websocket:
            if msg.startswith("selected_drone"):
                drone_id = msg.split()[1]
                selected_drone = drone_id
                await websocket.send(f"Выбран {selected_drone}. Открыт доступ к управлению")
            elif selected_drone:
                response = command.get(msg, "Неизвестная команда")
                await websocket.send(response)
            else:
                await websocket.send("Сначала выбери Квадрокоптер!")
    except ConnectionClosedError as e:
        logging.warning(f"Соединение с клиентом {client_ip}:{client_port} закрыто: {e}")
    except Exception as e:
        logging.error(f"Необработанная ошибка для {client_ip}:{client_port}: {e}")


async def main():
    start_server = await websockets.serve(control_drone, "localhost", 8765)
    logging.info(f"Сервер запущен и ожидает подключений")

    app = web.Application()
    app.router.add_get("/drones", get_drones)
    app.router.add_post("/drones/add", add_drone)
    app.router.add_post("/drones/delete", delete_drone)

    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })

    for route in list(app.router.routes()):
        cors.add(route)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8081)
    await site.start()

    try:
        await start_server.wait_closed()
    except ConnectionClosedError as e:
        logging.warning(f"Соединение с клиентом закрыто: {e}")
    except Exception as e:
        logging.error(f"Необработанная ошибка: {e}")


if __name__ == '__main__':
    asyncio.run(main())
