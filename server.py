import websockets
import asyncio
import logging
import signal
import aiohttp_cors
from aiohttp import web
from websockets.exceptions import ConnectionClosedError

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
drones = [
    {"id": "Квадрокоптер_1", "name": "Квадрокоптер 1"},
    {"id": "Квадрокоптер_2", "name": "Квадрокоптер 2"},
    {"id": "Квадрокоптер_3", "name": "Квадрокоптер 3"}
]

# Хранение состояний дронов (Паттерн "Состояние")
drones_locks = {}


# Обработка запроса на получение списка дронов (Паттерн "Посредник")
async def get_drones(request):
    return web.json_response(drones)


# Обработка управления дроном
async def control_drone(websocket):
    # Получение адреса клиента
    client_ip = websocket.remote_address[0]
    client_port = websocket.remote_address[1]
    logging.info(f"Подключен клиент: {client_ip}:{client_port}")

    # Команды для управления дроном (Паттерн "Команда")
    command = {
        "takeoff": "Квадрокоптер взлетает",
        "land": "Дрон приземляется",
        "hover": "Квадрокоптер завис",
        "move_forward": "Квадрокоптер летит вперед",
        "move_back": "Квадрокоптер летит назад",
        "move_left": "Квадрокоптер летит налево",
        "move_right": "Квадрокоптер летит направо",
        "move_turns_around_left": "Квадрокоптер поварачивается налево",
        "move_turns_around_right": "Квадрокоптер поварачивается направо",
        "start_engines": "Двигатели дрона запущены",
        "return_base": "Квадрокоптер возвращается на базу",
        "сargo_dumping": "Груз сброшен"
    }

    selected_drone = None  # Выбранный дрон

    try:
        async for msg in websocket:
            # Процесс выбора дрона
            if msg.startswith("selected_drone"):
                drone_id = msg.split()[1]  # Выделение id дрона
                # Проверка, доступен ли дрон
                if drone_id not in drones_locks:
                    drones_locks[drone_id] = (client_ip, client_port)  # Блокировка дрона
                    selected_drone = drone_id
                    await websocket.send(f"Выбран {selected_drone}. Открыт доступ к управлению")
                else:
                    client_locked = drones_locks[drone_id]
                    if client_locked == (client_ip, client_port):
                        await websocket.send(f"Вы уже управляете квадрокоптером!")
                    else:
                        await websocket.send(f"Квадрокоптер {drone_id} уже занят другим оператором")
            elif selected_drone:
                logging.info(f"{client_ip}:{client_port} отправил команду квадрокоптеру {selected_drone}: {msg}")
                # Выполнение команды
                response = command.get(msg, "Неизвестная команда")
                await websocket.send(response)
            else:
                await websocket.send("Сначала выбери Квадрокоптер!")

    except ConnectionClosedError as e:
        logging.warning(f"Соединение с клиентом {client_ip}:{client_port} закрыто: {e}")
    except Exception as e:
        logging.error(f"Необработанная ошибка для {client_ip}:{client_port}: {e}")
    finally:
        if selected_drone and drones_locks.get(selected_drone) == (client_ip, client_port):
            del drones_locks[selected_drone]  # Освобождение дрона
            logging.info(f"Квадрокоптер освобождён {selected_drone}")


# Завершение работы сервера (Паттерн "Наблюдатель" с обработкой сигналов)
async def shutdown_server(server, signal=None):
    if signal:
        logging.info(f"Получен сигнал завершения: {signal.name}")
        server.close()
        await server.wait_closed()
        logging.info(f"Сервер завершил работу")


# Основная функция
async def main():
    # Инициализация WebSocket-сервера
    start_server = await websockets.serve(control_drone, "localhost", 8765)
    logging.info(f"Сервер запущен и ожидает подключений")

    # Создание веб-приложения
    app = web.Application()
    app.router.add_get("/drones", get_drones)

    # Настройка CORS (Паттерн "Посредник")
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
    finally:
        # Очистка ресурсов при завершении
        start_server.close()
        await start_server.wait_closed()
        logging.error(f"Сервер завершил работу")


# Точка входа в программу
if __name__ == '__main__':
    asyncio.run(main())
