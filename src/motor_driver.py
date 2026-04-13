"""Pilote du moteur pour le déplacement de la caméra sur rail."""

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

class MotorDriver:
    def __init__(self, forward_pin=20, backward_pin=21, enable_pin=None):
        self.forward_pin = forward_pin
        self.backward_pin = backward_pin
        self.enable_pin = enable_pin
        self.pwm = None
        self.enabled = False

        if GPIO is None:
            return

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.forward_pin, GPIO.OUT)
            GPIO.setup(self.backward_pin, GPIO.OUT)

            if self.enable_pin is not None:
                GPIO.setup(self.enable_pin, GPIO.OUT)
                self.pwm = GPIO.PWM(self.enable_pin, 1000)
                self.pwm.start(0)

            self.stop()
            self.enabled = True
        except RuntimeError:
            self.enabled = False

    def _set_speed(self, speed):
        if self.pwm is not None and self.enabled:
            duty_cycle = max(0, min(100, int(speed)))
            self.pwm.ChangeDutyCycle(duty_cycle)

    def move_forward(self, speed=50):
        """Démarrer le déplacement vers l'avant."""
        if not self.enabled:
            raise RuntimeError('GPIO non disponible')

        GPIO.output(self.forward_pin, GPIO.HIGH)
        GPIO.output(self.backward_pin, GPIO.LOW)
        self._set_speed(speed)

    def move_backward(self, speed=50):
        """Démarrer le déplacement vers l'arrière."""
        if not self.enabled:
            raise RuntimeError('GPIO non disponible')

        GPIO.output(self.forward_pin, GPIO.LOW)
        GPIO.output(self.backward_pin, GPIO.HIGH)
        self._set_speed(speed)

    def stop(self):
        """Arrêter le moteur."""
        if not self.enabled:
            return

        GPIO.output(self.forward_pin, GPIO.LOW)
        GPIO.output(self.backward_pin, GPIO.LOW)
        if self.pwm is not None:
            self.pwm.ChangeDutyCycle(0)

    def calibrate(self):
        """Calibrer la position de référence du rail."""
        self.stop()
        return {'message': 'calibration automatique non implémentée'}

    def cleanup(self):
        """Libérer les GPIO."""
        if not self.enabled:
            return

        self.stop()
        if self.pwm is not None:
            self.pwm.stop()
        GPIO.cleanup()

    def _set_speed(self, speed):
        if self.pwm is not None:
            duty_cycle = max(0, min(100, int(speed)))
            self.pwm.ChangeDutyCycle(duty_cycle)

    def move_forward(self, speed=50):
        """Démarrer le déplacement vers l'avant."""
        GPIO.output(self.forward_pin, GPIO.HIGH)
        GPIO.output(self.backward_pin, GPIO.LOW)
        self._set_speed(speed)

    def move_backward(self, speed=50):
        """Démarrer le déplacement vers l'arrière."""
        GPIO.output(self.forward_pin, GPIO.LOW)
        GPIO.output(self.backward_pin, GPIO.HIGH)
        self._set_speed(speed)

    def stop(self):
        """Arrêter le moteur."""
        GPIO.output(self.forward_pin, GPIO.LOW)
        GPIO.output(self.backward_pin, GPIO.LOW)
        if self.pwm is not None:
            self.pwm.ChangeDutyCycle(0)

    def calibrate(self):
        """Calibrer la position de référence du rail."""
        self.stop()
        return {'message': 'calibration automatique non implémentée'}

    def cleanup(self):
        """Libérer les GPIO."""
        self.stop()
        if self.pwm is not None:
            self.pwm.stop()
        GPIO.cleanup()
