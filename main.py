import paho.mqtt.client as mqtt
import winsound
import time
import threading
import logging

# Audio volume imports
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    print("pycaw not found, absolute volume control will be disabled.")
    PYCAW_AVAILABLE = False

logging.basicConfig(level=logging.INFO)

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
TOPIC = "findmylaptop/jicam/command"

# Global event to stop the alarm
stop_event = threading.Event()
alarm_thread = None

def set_volume(level_percent):
    if not PYCAW_AVAILABLE:
        return
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        # Set scalar volume (0.0 to 1.0)
        vol_scalar = max(0.0, min(1.0, level_percent / 100.0))
        volume.SetMasterVolumeLevelScalar(vol_scalar, None)
        print(f"System volume set to {level_percent}%")
    except Exception as e:
        print(f"Failed to set volume: {e}")

def play_alarm():
    print("ALARM TRIGGERED! Playing sound...")
    # Loop for up to 5 minutes (600 * 0.5s) unless stopped
    for _ in range(600):
        if stop_event.is_set():
            print("Alarm stopped by user.")
            break
        winsound.Beep(2500, 500)
        time.sleep(0.1)
    else:
        print("Alarm timed out after 5 minutes.")

def trigger_alarm():
    global alarm_thread
    stop_event.clear()
    if alarm_thread is None or not alarm_thread.is_alive():
        alarm_thread = threading.Thread(target=play_alarm, daemon=True)
        alarm_thread.start()

def stop_alarm():
    stop_event.set()

# --- MQTT Setup ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("MQTT Connected successfully. Ready to receive web commands.")
        client.subscribe(TOPIC)
    else:
        print(f"MQTT Failed to connect, code {rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"MQTT Received: {payload}")
    
    cmd = payload.lower()
    if cmd == "ring":
        trigger_alarm()
    elif cmd == "stop":
        stop_alarm()
    elif cmd.startswith("vol:"):
        try:
            vol_val = int(cmd.split(":")[1])
            set_volume(vol_val)
        except ValueError:
            pass

def start_mqtt():
    # Sử dụng VERSION1 để tương thích với callback cũ
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"MQTT Error: {e}")

def main():
    print("--- FIND MY LAPTOP (Web Controller Mode) ---")
    # Start MQTT in a background thread
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()

    # Main loop (Keep process alive)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
