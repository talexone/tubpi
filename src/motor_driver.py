"""Pilote du moteur pour le déplacement de la caméra sur rail."""

import sys
import time
import RPi.GPIO as GPIO

class MotorDriver:
    def __init__(self, forward_pin=20, backward_pin=21):
        print('Initialiser les GPIO')
        self.forward_pin = forward_pin
        self.backward_pin = backward_pin
        self.enabled = False

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.forward_pin, GPIO.OUT)
            GPIO.setup(self.backward_pin, GPIO.OUT)

            self.stop()
            self.enabled = True
        except RuntimeError as exc:
            print(f'Impossible d’initialiser les GPIO : {exc}')
            self.enabled = False

    def move_forward(self):
        """Démarrer le déplacement vers l'avant."""
        if not self.enabled:
            raise RuntimeError('GPIO non disponible')

        GPIO.output(self.forward_pin, GPIO.HIGH)
        GPIO.output(self.backward_pin, GPIO.LOW)

    def move_backward(self):
        """Démarrer le déplacement vers l'arrière."""
        if not self.enabled:
            raise RuntimeError('GPIO non disponible')

        GPIO.output(self.forward_pin, GPIO.LOW)
        GPIO.output(self.backward_pin, GPIO.HIGH)

    def stop(self):
        """Arrêter le moteur."""
        if not self.enabled:
            return

        GPIO.output(self.forward_pin, GPIO.LOW)
        GPIO.output(self.backward_pin, GPIO.LOW)

    def calibrate(self):
        """Calibrer la position de référence du rail."""
        self.stop()
        return {'message': 'calibration automatique non implémentée'}

    def cleanup(self):
        """Libérer les GPIO."""
        if not self.enabled:
            return

        self.stop()
        GPIO.cleanup()

    def is_available(self):
        return self.enabled

    def check_gpio(self):
        """Vérifie si les GPIO ont été initialisés correctement."""
        return self.is_available()

    def run_test_sequence(self):
        """Exécute un test moteur : gauche 10s, droite 10s, arrêt."""
        if not self.enabled:
            raise RuntimeError('GPIO non disponible')

        print('Test moteur : aller gauche 10 secondes')
        self.move_backward()
        time.sleep(10)

        print('Test moteur : aller droit 10 secondes')
        self.move_forward()
        time.sleep(10)

        print('Arrêt du moteur')
        self.stop()


if __name__ == '__main__':
    driver = MotorDriver()
    if driver.is_available():
        if len(sys.argv) > 1 and sys.argv[1] == 'test':
            driver.run_test_sequence()
            driver.cleanup()
        else:
            print('GPIO disponible : initialisation réussie.')
            driver.cleanup()
    else:
        print('GPIO non disponible : vérifiez que le programme est exécuté sur un Raspberry Pi avec accès aux GPIO.')
