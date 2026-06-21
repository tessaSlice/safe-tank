#!/usr/bin/env python4
import rpi_gpio as GPIO
import time
import json
import os

SENSOR_DATA_FILE = "/tmp/sensor_data.json"
MAX_FILE_SIZE_BYTES = 64 * 1024  # 64 KB
OVERWRITE_INTERVAL_S = 300       # Overwrite file contents every 5 minutes

_file_start_time = time.time()
_vibration_active = False

DHTPIN = 17 # GPIO 17
VibratePin = 16
Gpin = 27
Rpin = 18

GPIO.setmode(GPIO.BCM)

MAX_UNCHANGE_COUNT = 100

STATE_INIT_PULL_DOWN = 1
STATE_INIT_PULL_UP = 2
STATE_DATA_FIRST_PULL_DOWN = 3
STATE_DATA_PULL_UP = 4
STATE_DATA_PULL_DOWN = 5

def read_dht11_dat():
    # Begin start sequence

    # First HIGH
    # We "setup" the GPIO pin as output, and we specify the level at the same time.
    # This avoids a delay between setting up the pin and setting the level
    GPIO.setup(DHTPIN, GPIO.OUT)
    GPIO.output(DHTPIN, GPIO.HIGH)
    time.sleep(0.05)
 
    # Then, LOW for at least 18ms (we use 0.02s which is 20ms)
    GPIO.output(DHTPIN, GPIO.LOW)
    time.sleep(0.02)

    # Wait for the response from DHT11.
    # (No pull-up needed, they are already installed on the sensor board)
    #GPIO.setup(DHTPIN, GPIO.IN)
    # The following line does the same but activates the pull-up some DHT11 board need (not ours!)
    GPIO.setup(DHTPIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    unchanged_count = 0
    last = -1
    data = []
    while True:
        current = GPIO.input(DHTPIN)
        data.append(current)
        if last != current:
            unchanged_count = 0
            last = current
        else:
            unchanged_count += 1
            if unchanged_count > MAX_UNCHANGE_COUNT:
                break

    state = STATE_INIT_PULL_DOWN

    lengths = []
    current_length = 0

    for current in data:
        current_length += 1

        if state == STATE_INIT_PULL_DOWN:
            if current == GPIO.LOW:
                state = STATE_INIT_PULL_UP
            else:
                continue
        if state == STATE_INIT_PULL_UP:
            if current == GPIO.HIGH:
                state = STATE_DATA_FIRST_PULL_DOWN
            else:
                continue
        if state == STATE_DATA_FIRST_PULL_DOWN:
            if current == GPIO.LOW:
                state = STATE_DATA_PULL_UP
            else:
                continue
        if state == STATE_DATA_PULL_UP:
            if current == GPIO.HIGH:
                current_length = 0
                state = STATE_DATA_PULL_DOWN
            else:
                continue
        if state == STATE_DATA_PULL_DOWN:
            if current == GPIO.LOW:
                lengths.append(current_length)
                state = STATE_DATA_PULL_UP
            else:
                continue
    if len(lengths) != 40:
        print ("Data not good, skip")
        return False

    shortest_pull_up = min(lengths)
    longest_pull_up = max(lengths)
    halfway = (longest_pull_up + shortest_pull_up) / 2
    bits = []
    the_bytes = []
    byte = 0

    for length in lengths:
        bit = 0
        if length > halfway:
            bit = 1
        bits.append(bit)
    #print ("bits: %s, length: %d" % (bits, len(bits)))
    for i in range(0, len(bits)):
        byte = byte << 1
        if (bits[i]):
            byte = byte | 1
        else:
            byte = byte | 0
        if ((i + 1) % 8 == 0):
            the_bytes.append(byte)
            byte = 0
    #print (the_bytes)
    checksum = (the_bytes[0] + the_bytes[1] + the_bytes[2] + the_bytes[3]) & 0xFF
    if the_bytes[4] != checksum:
        print ("Data not good, skip")
        return False

    return the_bytes[0], the_bytes[2]

def Led(x):
    if x == 0:
        GPIO.output(Rpin, 0)
        GPIO.output(Gpin, 1)
    if x == 1:
        GPIO.output(Rpin, 1)
        GPIO.output(Gpin, 0)

last_red_time = time.time()

def write_sensor_data(humidity=None, temperature=None, vibration=False):
    global _file_start_time

    now = time.time()
    elapsed = now - _file_start_time
    file_too_old = elapsed >= OVERWRITE_INTERVAL_S
    file_too_large = (os.path.exists(SENSOR_DATA_FILE) and
                      os.path.getsize(SENSOR_DATA_FILE) > MAX_FILE_SIZE_BYTES)

    if file_too_old or file_too_large:
        _file_start_time = now

    reading = {"timestamp": now, "vibration": vibration}
    if humidity is not None:
        reading["humidity"] = humidity
    if temperature is not None:
        reading["temperature"] = temperature

    if file_too_old or file_too_large or not os.path.exists(SENSOR_DATA_FILE):
        data = {"readings": [reading]}
    else:
        try:
            with open(SENSOR_DATA_FILE, "r") as f:
                data = json.load(f)
            data["readings"].append(reading)
        except (json.JSONDecodeError, KeyError, IOError):
            data = {"readings": [reading]}

    with open(SENSOR_DATA_FILE, "w") as f:
        json.dump(data, f)


def handle_vibration(x):
    global _vibration_active
    print ("vibration detected")
    _vibration_active = True
    last_red_time = time.time()
    led_state = 0
    Led(led_state)

def main():
    global _vibration_active
    GPIO.setup(Gpin, GPIO.OUT)
    GPIO.setup(Rpin, GPIO.OUT)
    GPIO.setup(VibratePin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(VibratePin, GPIO.RISING, callback=handle_vibration)
    led_state = 1
    while True:
        result = read_dht11_dat()
        print ("led state = ", led_state)
        if (time.time() - last_red_time) >= 1000:
            led_state = 1
        Led(led_state)

        humidity = None
        temperature = None
        if result:
            humidity, temperature = result
            print ("humidity: %s %%,  Temperature: %s °C" % (humidity, temperature))

        write_sensor_data(humidity=humidity, temperature=temperature,
                          vibration=_vibration_active)
        _vibration_active = False
        time.sleep(2)

def destroy():
    GPIO.cleanup()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        destroy() 
