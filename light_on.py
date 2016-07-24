#!/usr/bin/env python
import RPi.GPIO as GPIO

LightPin = 15  # light pin

GPIO.setmode(GPIO.BOARD)
GPIO.setup(LightPin, GPIO.OUT)
GPIO.output(LightPin, GPIO.LOW)

try:
    while True:
        GPIO.output(LightPin, GPIO.HIGH)
except KeyboardInterrupt:
    GPIO.output(LightPin, GPIO.LOW)
    GPIO.cleanup()
