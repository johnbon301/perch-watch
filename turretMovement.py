from adafruit_servokit import ServoKit
from gpiozero import DigitalOutputDevice
from time import sleep

class Turret:
    def __init__(self, panAngle, tiltAngle):
        self.panAngle = panAngle
        self.tiltAngle = tiltAngle
        self.kit = ServoKit(channels=16)
        self.trigger = DigitalOutputDevice(17)
        

    def moveTurret(self, panAngle, tiltAngle):
        if panAngle is not None:
            self.kit.servo[0].angle = panAngle # based on middle box coordinate of ai model
            self.panAngle = panAngle
            print(self.panAngle)
        if tiltAngle is not None:
            self.kit.servo[1].angle = tiltAngle # MAX ANGLE(up and down) 80 - 180
            self.tiltAngle = tiltAngle
            print(self.tiltAngle)

        return self.panAngle, self.tiltAngle
      
    def shoot(self):
        self.trigger.on()
        sleep(2)
        self.trigger.off()


