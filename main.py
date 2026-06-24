import paho.mqtt.client as mqtt
import winsound
import time
import threading
import logging
import math
import io
import wave
import struct

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

timer_thread = None

# Hàm tạo một file âm thanh WAV cảnh báo (Lưu trực tiếp trong RAM)
# Giải quyết vấn đề winsound.Beep không bị ảnh hưởng bởi Âm lượng hệ thống
def generate_alarm_wav():
    framerate = 44100
    duration = 1.0 # 1 giây cho 1 chu kỳ
    num_samples = int(framerate * duration)
    
    audio_data = bytearray()
    for i in range(num_samples):
        # 0.25s đầu: Âm tần 2000Hz (Bíp thấp)
        # 0.25s sau: Âm tần 2500Hz (Bíp cao)
        # 0.5s cuối: Im lặng
        if i < 11025:
            value = int(32767.0 * math.sin(2.0 * math.pi * 2000.0 * i / framerate))
        elif i < 22050:
            value = int(32767.0 * math.sin(2.0 * math.pi * 2500.0 * i / framerate))
        else:
            value = 0
        audio_data += struct.pack('<h', value)
        
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2) # 16-bit
        wav_file.setframerate(framerate)
        wav_file.writeframes(audio_data)
        
    return wav_io.getvalue()

print("Đang tạo bộ nhớ đệm âm thanh cảnh báo...")
ALARM_WAV_DATA = generate_alarm_wav()

def set_volume(level_percent):
    if not PYCAW_AVAILABLE:
        return
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        # Chỉnh âm lượng tổng (Master Volume)
        vol_scalar = max(0.0, min(1.0, level_percent / 100.0))
        volume.SetMasterVolumeLevelScalar(vol_scalar, None)
        print(f"System volume set to {level_percent}%")
    except Exception as e:
        print(f"Failed to set volume: {e}")

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
    
    # Phát file WAV trong RAM lặp đi lặp lại một cách không đồng bộ (Bắt buộc dùng SND_ASYNC)
    winsound.PlaySound(ALARM_WAV_DATA, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_LOOP)
    
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
