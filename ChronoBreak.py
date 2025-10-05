from lcu_driver import Connector
import json
import asyncio
import os

class AppState:
    def __init__(self):
        self.consecutive_losses = 0
        self.lockout_threshold = 2
APP_STATE = AppState()


async def load_state():
    loop = asyncio.get_event_loop()
    try:
        with await loop.run_in_executor(None, open, "losses.json", "r") as file:
            data = await loop.run_in_executor(None, json.load, file)
            APP_STATE.consecutive_losses = data.get("consecutive_losses", 0)
            APP_STATE.lockout_threshold = data.get("lockout_threshold", 2)
            print(f"State loaded. Losses: {APP_STATE.consecutive_losses}, Threshold: {APP_STATE.lockout_threshold}")
    except FileNotFoundError:
        print("losses.json not found. Creating new state with default threshold (2).")
        await save_state()

async def save_state():
    loop = asyncio.get_event_loop()
    data = {
        "consecutive_losses": APP_STATE.consecutive_losses,
        "lockout_threshold": APP_STATE.lockout_threshold
    }
    with await loop.run_in_executor(None, open, "losses.json", "w") as file:
        await loop.run_in_executor(None, json.dump, data, file, indent=4)
        print(f"State saved. Losses: {APP_STATE.consecutive_losses}, Threshold: {APP_STATE.lockout_threshold}")

connector = Connector()

@connector.ready
async def connect(connection):
    await load_state()
    print('LCU API is ready to be used.')


@connector.ws.register('/lol-gameflow/v1/gameflow-phase', event_types=('UPDATE',))
async def on_game_phase_update(connection, event):

    if event.data == 'EndOfGame':
        await asyncio.sleep(2)
        response = await connection.request('GET', '/lol-end-of-game/v1/eog-stats-block')
        result_object = await response.json()
        is_ranked_solo_duo = result_object.get("queueType") == "RANKED_SOLO_5x5"
        is_loss = result_object.get("localPlayer", {}).get("stats", {}).get("LOSE") == 1

        if is_ranked_solo_duo and is_loss:
            APP_STATE.consecutive_losses += 1
            await save_state()

            if APP_STATE.consecutive_losses >= APP_STATE.lockout_threshold:
                print("LOCKOUT TRIGGERED")
                # **TODO:** Implement Lockout
                pass

        elif is_ranked_solo_duo and not is_loss:
            if APP_STATE.consecutive_losses > 0:
                print("Win detected. Resetting loss counter.")
                APP_STATE.consecutive_losses = 0
                await save_state()





@connector.close
async def disconnect(_):
    print('The client have been closed!')

connector.start()
