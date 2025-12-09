import asyncio, json, pyautogui, mss
pyautogui.FAILSAFE = False
from PIL import Image
from io import BytesIO
import websockets
import numpy as np
from urllib.parse import urlparse, parse_qs
import soundcard as sc
import threading

# pip install pyautogui mss pillow websockets numpy soundcard

FPS = 30
JPEG_QUALITY = 25
PASSWORD = "1234567890"

# audio config
AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 1
AUDIO_CHUNK = 4096

sct = mss.mss()
held_keys = set()
clients_frames = set()
frame_queue = asyncio.Queue(maxsize=1)
audio_queue = asyncio.Queue(maxsize=32)
async def capture_screen_loop():
    monitor = sct.monitors[0]
    while True:
        img = sct.grab(monitor)
        img = Image.frombytes("RGB", (img.width, img.height), img.rgb)
        img = img.resize((img.width, img.height), Image.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY)
        frame_data = buffer.getvalue()

        if frame_queue.full():
            try: frame_queue.get_nowait()
            except: pass
        await frame_queue.put((frame_data, img.width, img.height))
        await asyncio.sleep(1 / FPS)
def audio_thread(queue):
    devices = sc.all_microphones(include_loopback=True)
    loopback_device = None
    for d in devices:
        if getattr(d, "isloopback", False) or "loopback" in d.name.lower():
            loopback_device = d
            break

    if loopback_device is None:
        loopback_device = sc.default_speaker()
        print("No loopback detected, using default speaker (may not capture audio)")

    print("Using loopback device:", loopback_device.name)

    try:
        with loopback_device.recorder(samplerate=AUDIO_SAMPLE_RATE, channels=AUDIO_CHANNELS) as rec:
            while True:
                data = rec.record(numframes=AUDIO_CHUNK)
                int_data = (data * 32767).astype('<i2')
                try:
                    queue.put_nowait(int_data)
                except asyncio.QueueFull:
                    pass
    except Exception as e:
        print("Audio recorder error:", e)

async def capture_audio_loop():
    threading.Thread(target=audio_thread, args=(audio_queue,), daemon=True).start()
    while True:
        await asyncio.sleep(1)  # keep alive
async def frame_handler(websocket):
    while True:
        try:
            frame, w, h = await frame_queue.get()
            await websocket.send(json.dumps({"type": "size", "w": w, "h": h, "scale": 1}))
            await websocket.send(frame)
        except websockets.ConnectionClosed:
            break

async def cursor_tracker():
    while True:
        try:
            x, y = pyautogui.position()
            packet = json.dumps({"type": "cursor", "x": x, "y": y})
            for ws in list(clients_frames):
                try: await ws.send(packet)
                except: pass
        except:
            pass
        await asyncio.sleep(0.05)

async def audio_handler(websocket):
    meta = {
        "type":"audio-info",
        "rate": AUDIO_SAMPLE_RATE,
        "channels": AUDIO_CHANNELS,
        "chunk": AUDIO_CHUNK
    }
    try:
        await websocket.send(json.dumps(meta))
    except:
        return

    while True:
        try:
            data = await audio_queue.get()
            arr = np.asarray(data)
            if arr.ndim == 1:
                arr = arr.reshape(-1, 1)
            arr = arr.astype('<i2')
            await websocket.send(arr.reshape(-1).tobytes())
        except websockets.ConnectionClosed:
            break
        except Exception as e:
            print("audio send error:", e)
            await asyncio.sleep(0.01)

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
                key_map = {"Control":"ctrl","Shift":"shift","Alt":"alt",
                           "Escape":"esc","Enter":"enter","Backspace":"backspace",
                           "Tab":"tab","ArrowUp":"up","ArrowDown":"down",
                           "ArrowLeft":"left","ArrowRight":"right"}
                key_to_press = key_map.get(key, key)
                if action=="down" and key_to_press not in held_keys:
                    pyautogui.keyDown(key_to_press); held_keys.add(key_to_press)
                elif action=="up" and key_to_press in held_keys:
                    pyautogui.keyUp(key_to_press); held_keys.discard(key_to_press)
                elif action=="press":
                    pyautogui.press(key_to_press)
            elif data.get("type") == "type":
                txt = data.get("text", "")
                if txt:
                    await async_type(txt)
        except Exception as e:
            print("input handler error:", e)
async def handler(websocket):
    path_full = websocket.request.path
    parsed = urlparse(path_full)
    path = parsed.path
    qs = parse_qs(parsed.query)
    passwd_q = qs.get("passwd", [None])[0]

    if websocket.subprotocol != PASSWORD and passwd_q != PASSWORD:
        await websocket.close(code=4001, reason="password entered was incorrect")
        return

    if path == "/input":
        await input_handler(websocket)
    elif path == "/audio":
        await audio_handler(websocket)
    else:
        clients_frames.add(websocket)
        try:
            await frame_handler(websocket)
        finally:
            clients_frames.discard(websocket)
async def main():
    asyncio.create_task(capture_screen_loop())
    asyncio.create_task(cursor_tracker())
    asyncio.create_task(capture_audio_loop())

    async with websockets.serve(handler, "0.0.0.0", 8765,
                                max_size=50_000_000,
                                subprotocols=[PASSWORD]):
        print("live")
        print("use ws://localhost:8765 in https://gixtuh.vercel.app/viewer to use VNC")
        print("HOSTING THE WEBSOCKET TO THE PUBLIC IS NOT RECOMMENDED")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
