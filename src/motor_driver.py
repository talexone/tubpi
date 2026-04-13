"""Pilote du moteur pour le déplacement de la caméra sur rail."""
import RPi.GPIO as GPIO

R1=20 # m1
R2=21 # m2

GPIO.setup(R1, GPIO.OUT)  
GPIO.setup(R2, GPIO.OUT)

class MotorDriver:
    def __init__(self, enable_pin=None, forward_pin=None, backward_pin=None):
        self.enable_pin = enable_pin
        self.forward_pin = forward_pin
        self.backward_pin = backward_pin
        # TODO: initialiser les GPIO

    def move_forward(self, speed=50):
        """Démarrer le déplacement vers l'avant."""
        GPIO.output(L1, GPIO.HIGH)
        GPIO.output(L2, GPIO.LOW)

    def move_backward(self, speed=50):
        """Démarrer le déplacement vers l'arrière."""
        GPIO.output(L1, GPIO.LOW)
        GPIO.output(L2, GPIO.HIGH)

    def stop(self):
        """Arrêter le moteur."""
        GPIO.output(L1, GPIO.LOW)
        GPIO.output(L2, GPIO.LOW)

    def calibrate(self):
        """Calibrer la position de référence du rail."""
        raise NotImplementedError