import asyncio, json, pyautogui, mss
pyautogui.FAILSAFE = False
from PIL import Image
from io import BytesIO
import websockets

# pip install pyautogui mss pillow websockets

FPS = 30
SCALE = 1
JPEG_QUALITY = 25
sct = mss.mss()
held_keys = set()
clients_frames = set()

frame_queue = asyncio.Queue(maxsize=1)
async def capture_screen_loop():
    monitor = sct.monitors[0]
    while True:
        img = sct.grab(monitor)
        img = Image.frombytes("RGB", (img.width, img.height), img.rgb)
        new_w, new_h = int(img.width*SCALE), int(img.height*SCALE)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY)
        frame_data = buffer.getvalue()

        if frame_queue.full():
            try: frame_queue.get_nowait()
            except: pass
        await frame_queue.put((frame_data, img.width, img.height))
        await asyncio.sleep(1 / FPS)

async def frame_handler(websocket):
    while True:
        try:
            frame, w, h = await frame_queue.get()
            await websocket.send(json.dumps({"type": "size", "w": w, "h": h, "scale": SCALE}))
            await websocket.send(frame)
        except websockets.ConnectionClosed:
            break
        
async def cursor_tracker():
    while True:
        try:
            x, y = pyautogui.position()
            packet = json.dumps({"type": "cursor", "x": x, "y": y})
            for ws in list(clients_frames):
                try:
                    await ws.send(packet)
                except:
                    pass
        except:
            pass
        await asyncio.sleep(0.05)

        
async def run_blocking(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
async def async_type(text):
    await run_blocking(pyautogui.typewrite, text)

async def input_handler(websocket):
    async for message in websocket:
        try:
            data = json.loads(message)
            if data.get("type") == "mouse":
                x, y = data["x"], data["y"]
                pyautogui.moveTo(x, y)
                button = data.get("button", "left")
                state = data.get("state")
                if state == "down": pyautogui.mouseDown(button=button)
                elif state == "up": pyautogui.mouseUp(button=button)
                elif data.get("click"): pyautogui.click(button=button)
            elif data.get("type") == "keyboard":
                key = data["key"]
                action = data.get("action", "press")
                key_map = {
                    "Control":"ctrl","Shift":"shift","Alt":"alt",
                    "Escape":"esc","Enter":"enter","Backspace":"backspace",
                    "Tab":"tab","ArrowUp":"up","ArrowDown":"down",
                    "ArrowLeft":"left","ArrowRight":"right"
                }
                key_to_press = key_map.get(key, key)
                if action=="down" and key_to_press not in held_keys:
                    pyautogui.keyDown(key_to_press); held_keys.add(key_to_press)
                elif action=="up" and key_to_press in held_keys:
                    pyautogui.keyUp(key_to_press); held_keys.discard(key_to_press)
                elif action == "press":
                    pyautogui.press(key_to_press)
            elif data.get("type") == "type":
                txt = data.get("text", "")
                if txt:
                    await async_type(txt)

        except Exception as e:
            print("error:", e)

async def handler(websocket):
    path = websocket.request.path
    if path == "/input":
        await input_handler(websocket)
    else:
        clients_frames.add(websocket)
        try:
            await frame_handler(websocket)
        finally:
            clients_frames.discard(websocket)


async def main():
    asyncio.create_task(capture_screen_loop())
    asyncio.create_task(cursor_tracker())

    async with websockets.serve(handler, "0.0.0.0", 8765, max_size=50_000_000):
        print("live")
        print("use ws://localhost:8765 to in https://gixtuh.vercel.app/viewer to use vnc")
        print("HOSTING THE WEBSOCKET TO THE PUBLIC IS NOT RECOMMENDED")
        await asyncio.Future()


asyncio.run(main())
