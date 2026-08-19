from adafruit_servokit import ServoKit
from gpiozero import DigitalOutputDevice
from time import sleep


# class Turret:
#     def __init__(self, angle):
#         self.panAngle = panAngle
#         self.tiltAngle = tiltAngle
#         self.kit = ServoKit(channels=16)

#     def moveTurret(self):
#         kit.servo[0].angle = self.angle # based on middle box coordinate of ai model
#         kit.servo[1].angle = self.angle # MAX ANGLE(up and down) 80 - 180



kit = ServoKit(channels=16)
trigger = DigitalOutputDevice(17)  # GPIO pin

# Servo check
kit.servo[0].angle = 90
kit.servo[1].angle = 90
sleep(5)

# Pump check
trigger.on()
sleep(1.5)
trigger.off()
