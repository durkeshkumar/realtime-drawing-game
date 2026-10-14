
import asyncio
import json

import websockets


async def main():
    room_code = input("Enter room code: ").strip().upper()
    player_id = int(input("Enter active player ID: "))

    url = (
        f"ws://127.0.0.1:8000/ws/rooms/{room_code}"
        f"?player_id={player_id}"
    )

    try:
        async with websockets.connect(url) as websocket:
            print("Connected to WebSocket!")

            connected = json.loads(await websocket.recv())
            print("Connection event:", connected)

            room_event = json.loads(await websocket.recv())
            print("Room event:", room_event)

            await websocket.send(json.dumps({"type": "ping"}))

            pong = json.loads(await websocket.recv())
            print("Ping test:", pong)

    except Exception as exc:
        print(f"WebSocket test failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
