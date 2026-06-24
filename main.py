import paho.mqtt.client as mqtt
import winsound
import time
import threading
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
TOPIC = "findmylaptop/jicam/command"

def play_alarm():
    print("ALARM TRIGGERED! Playing sound...")
    for _ in range(5):
        winsound.Beep(2500, 500)
        time.sleep(0.1)

def trigger_alarm():
    threading.Thread(target=play_alarm, daemon=True).start()

# --- MQTT Setup ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("MQTT Connected successfully.")
        client.subscribe(TOPIC)
    else:
        print(f"MQTT Failed to connect, code {rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"MQTT Received: {payload}")
    if payload.lower() == "ring":
        trigger_alarm()

def start_mqtt():
    # Sử dụng VERSION1 để tương thích với callback cũ và tắt warning
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"MQTT Error: {e}")

# --- BLE Setup (Optional fallback) ---
try:
    from bless import (
        BlessServer,
        BlessGATTCharacteristic,
        GATTCharacteristicProperties,
        GATTAttributePermissions,
    )
    BLE_AVAILABLE = True
except ImportError as e:
    print(f"BLE dependencies not fully supported ({e}).")
    print(">>> Running in MQTT-only mode (Web Controller) <<<")
    BLE_AVAILABLE = False

if BLE_AVAILABLE:
    SERVICE_UUID = "A07498CA-AD5B-474E-940D-16F1FBE7E8CD"
    CHAR_UUID = "51FF12BB-3ED8-46E5-B4F9-D64E2FEC021B"

    def read_request(characteristic: BlessGATTCharacteristic, **kwargs) -> bytearray:
        return bytearray(b"Ready")

    def write_request(characteristic: BlessGATTCharacteristic, value: bytearray, **kwargs):
        print(f"BLE Received: {value}")
        if value == b"ring":
            trigger_alarm()

    async def run_ble():
        server_name = "FindMyLaptop"
        server = BlessServer(name=server_name)
        
        await server.add_new_service(SERVICE_UUID)
        await server.add_new_characteristic(
            SERVICE_UUID,
            CHAR_UUID,
            (GATTCharacteristicProperties.read | GATTCharacteristicProperties.write),
            value=bytearray(b"Ready"),
            permissions=(GATTAttributePermissions.readable | GATTAttributePermissions.writeable),
        )
        
        server.read_request_func = read_request
        server.write_request_func = write_request
        
        print(f"Starting BLE Server: {server_name}")
        await server.start()
        print("BLE Server started. Advertising...")
        
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await server.stop()
else:
    async def run_ble():
        print("Waiting for MQTT commands indefinitely...")
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

def main():
    # Start MQTT in a background thread
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()

    # Run BLE (or idle loop) in the main asyncio event loop
    try:
        asyncio.run(run_ble())
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
