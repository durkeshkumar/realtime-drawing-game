
import asyncio
import json

import websockets


BASE_URL = "ws://127.0.0.1:8000/ws/rooms"


async def main():
    room_code = input("Room code: ").strip().upper()
    player1_id = int(input("Player 1 ID: "))
    player2_id = int(input("Player 2 ID: "))

    url1 = f"{BASE_URL}/{room_code}?player_id={player1_id}"
    url2 = f"{BASE_URL}/{room_code}?player_id={player2_id}"

    async with websockets.connect(url1) as player1:
        print("Player 1 connected")
        print("Player 1 event:", json.loads(await player1.recv()))
        print("Player 1 event:", json.loads(await player1.recv()))

        async with websockets.connect(url2) as player2:
            print("Player 2 connected")

            # Player 1 should receive player 2's connection event.
            event1 = json.loads(await asyncio.wait_for(player1.recv(), 3))
            print("Player 1 received:", event1)

            # Player 2 receives its own initial events.
            event2 = json.loads(await player2.recv())
            event3 = json.loads(await player2.recv())
            print("Player 2 event:", event2)
            print("Player 2 event:", event3)

            assert event1["type"] == "player_connected"
            assert event1["player_id"] == player2_id

            print("SUCCESS: Player 1 received Player 2's connection event!")


if __name__ == "__main__":
    asyncio.run(main())
