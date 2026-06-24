import paho.mqtt.client as mqtt
import winsound
import time
import threading
import logging
import math
import os
import wave
import struct

# Audio volume imports
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    print("pycaw not found, absolute volume control will be disabled.")
    PYCAW_AVAILABLE = False

logging.basicConfig(level=logging.INFO)

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
TOPIC = "findmylaptop/jicam/command"

timer_thread = None
ALARM_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alarm.wav")

# Hàm tạo một file âm thanh WAV cảnh báo và lưu ra ổ đĩa
# Giải quyết lỗi "Cannot play asynchronously from memory" của thư viện winsound
def generate_alarm_wav():
    framerate = 44100
    duration = 1.0 # 1 giây cho 1 chu kỳ
    num_samples = int(framerate * duration)
    
    audio_data = bytearray()
    for i in range(num_samples):
        if i < 11025:
            value = int(32767.0 * math.sin(2.0 * math.pi * 2000.0 * i / framerate))
        elif i < 22050:
            value = int(32767.0 * math.sin(2.0 * math.pi * 2500.0 * i / framerate))
        else:
            value = 0
        audio_data += struct.pack('<h', value)
        
    with wave.open(ALARM_FILE, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2) # 16-bit
        wav_file.setframerate(framerate)
        wav_file.writeframes(audio_data)

print("Đang tạo file âm thanh cảnh báo...")
generate_alarm_wav()

def set_volume(level_percent):
    if not PYCAW_AVAILABLE:
        return
    try:
        # MQTT gọi hàm này từ một luồng (thread) khác, nên ta phải khởi tạo COM thread
        CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.EndpointVolume
        # Chỉnh âm lượng tổng (Master Volume)
        vol_scalar = max(0.0, min(1.0, level_percent / 100.0))
        interface.SetMasterVolumeLevelScalar(vol_scalar, None)
        print(f"System volume set to {level_percent}%")
    except Exception as e:
        print(f"Failed to set volume: {e}")
    finally:
        CoUninitialize()

def stop_alarm():
    global timer_thread
    # Phát một âm thanh Rỗng (None) với cờ PURGE để DỪNG NGAY LẬP TỨC âm thanh đang phát
    winsound.PlaySound(None, winsound.SND_PURGE)
    if timer_thread is not None:
        timer_thread.cancel()
        timer_thread = None
    print("Alarm stopped.")

def trigger_alarm():
    global timer_thread
    print("ALARM TRIGGERED! Phát âm thanh cảnh báo...")
    # Dừng âm thanh cũ (nếu có)
    stop_alarm()
    
    # Phát file WAV trên đĩa cứng lặp đi lặp lại một cách không đồng bộ
    winsound.PlaySound(ALARM_FILE, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
    
    # Hẹn giờ tự tắt sau 5 phút (300 giây) để tránh tốn pin nếu người dùng quên tắt
    timer_thread = threading.Timer(300, stop_alarm)
    timer_thread.start()

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
