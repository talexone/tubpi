"""Pilote du moteur pour le déplacement de la caméra sur rail."""

import sys
import time
import threading
import RPi.GPIO as GPIO

class MotorDriver:
    # Ramp configuration
    PWM_FREQ = 1000        # Hz
    RAMP_STEPS = 20        # number of steps 0 → 100 %
    RAMP_STEP_DELAY = 0.02 # seconds between steps (~0.4 s total ramp time)
    
    # Encoder configuration
    # Distance par impulsion (en mm) - à ajuster selon votre système mécanique
    # Formule : (circonférence de la poulie en mm) / (impulsions par tour de l'encodeur)
    MM_PER_PULSE = 0.1  # Valeur par défaut, à calibrer

    def __init__(self, forward_pin=20, backward_pin=21, pwm_pin=26, 
                 limit_forward_pin=24, limit_backward_pin=23,
                 encoder_a_pin=17, encoder_b_pin=27, encoder_index_pin=22,
                 enable_encoder=True):
        print("Initialiser les GPIO")
        self.forward_pin = forward_pin
        self.backward_pin = backward_pin
        self._pwm_pin = pwm_pin
        # GPIO 24 : capteur devant (forward) - se déclenche en premier lors du mouvement vers l'avant
        # GPIO 23 : capteur reculé (backward) - se déclenche en premier lors du mouvement vers l'arrière
        self.limit_forward_pin = limit_forward_pin
        self.limit_backward_pin = limit_backward_pin
        
        # Encodeur de position
        self.encoder_enabled = enable_encoder
        self.encoder_a_pin = encoder_a_pin
        self.encoder_b_pin = encoder_b_pin
        self.encoder_index_pin = encoder_index_pin
        
        # Variables de suivi de position
        self._encoder_position = 0      # Position actuelle en impulsions (peut être négatif)
        self._encoder_total_pulses = 0  # Distance totale parcourue en impulsions (toujours positif)
        self._encoder_session_pulses = 0  # Distance depuis le démarrage
        self._encoder_last_a = 0
        self._encoder_last_b = 0
        self._encoder_lock = threading.Lock()
        
        self._pwm = None
        self._duty = 0          # current duty cycle (0-100)
        self._current_fwd = False   # current forward pin state
        self._current_bwd = False   # current backward pin state
        self._lock = threading.Lock()   # serializes commands
        self._cancel = threading.Event()  # signals ramp loops to stop early
        self.enabled = False

        try:
            GPIO.setmode(GPIO.BCM)
            # Spécifier initial=GPIO.LOW pour éviter le bug rpi-lgpio sur Pi 5
            # qui essaie de lire l'état avant allocation
            GPIO.setup(self.forward_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.backward_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self._pwm_pin, GPIO.OUT, initial=GPIO.LOW)
            
            # Configuration des capteurs de fin de course
            # Pull-up interne : HIGH quand libre, LOW quand déclenché
            GPIO.setup(self.limit_forward_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self.limit_backward_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Configuration de l'encodeur (optionnel)
            if self.encoder_enabled:
                # Les signaux viennent du Level Shifter (5V -> 3.3V)
                GPIO.setup(self.encoder_a_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.setup(self.encoder_b_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.setup(self.encoder_index_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                
                # Lire l'état initial de l'encodeur
                self._encoder_last_a = GPIO.input(self.encoder_a_pin)
                self._encoder_last_b = GPIO.input(self.encoder_b_pin)
                
                # Configurer les interruptions sur les canaux A et B (détection de front)
                # bouncetime=1ms pour limiter la fréquence et éviter les rebonds
                GPIO.add_event_detect(self.encoder_a_pin, GPIO.BOTH, callback=self._encoder_callback, bouncetime=1)
                GPIO.add_event_detect(self.encoder_b_pin, GPIO.BOTH, callback=self._encoder_callback, bouncetime=1)
                print("Encodeur activé avec bouncetime=1ms")
            else:
                print("Encodeur désactivé")

            self._pwm = GPIO.PWM(self._pwm_pin, self.PWM_FREQ)
            self._pwm.start(0)

            GPIO.output(self.forward_pin, GPIO.LOW)
            GPIO.output(self.backward_pin, GPIO.LOW)
            self._current_fwd = GPIO.LOW
            self._current_bwd = GPIO.LOW
            self.enabled = True
        except RuntimeError as exc:
            print(f"Impossible d'initialiser les GPIO : {exc}")
            self.enabled = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encoder_callback(self, channel):
        """
        Callback pour les interruptions de l'encodeur en quadrature.
        Détermine la direction et met à jour les compteurs.
        Optimisé pour être rapide et ne pas bloquer le thread principal.
        """
        if not self.encoder_enabled:
            return
        
        # Utiliser trylock pour ne pas bloquer si occupé
        if not self._encoder_lock.acquire(blocking=False):
            return  # Skip this interrupt if we can't get the lock immediately
        
        try:
            # Lire l'état actuel des deux canaux
            a = GPIO.input(self.encoder_a_pin)
            b = GPIO.input(self.encoder_b_pin)
            
            # Déterminer la direction en comparant l'état actuel avec le précédent
            # Encodeur en quadrature : quand A change, si B=0 on avance, si B=1 on recule
            # Quand B change, si A=1 on avance, si A=0 on recule
            if channel == self.encoder_a_pin and a != self._encoder_last_a:
                if a == b:
                    # Rotation inverse (backward)
                    self._encoder_position -= 1
                else:
                    # Rotation avant (forward)
                    self._encoder_position += 1
                self._encoder_total_pulses += 1
                self._encoder_session_pulses += 1
                self._encoder_last_a = a
            elif channel == self.encoder_b_pin and b != self._encoder_last_b:
                if a == b:
                    # Rotation avant (forward)
                    self._encoder_position += 1
                else:
                    # Rotation inverse (backward)
                    self._encoder_position -= 1
                self._encoder_total_pulses += 1
                self._encoder_session_pulses += 1
                self._encoder_last_b = b
        finally:
            self._encoder_lock.release()

    def _is_limit_forward_triggered(self):
        """Vérifie si le capteur de fin de course avant est déclenché."""
        if not self.enabled:
            return False
        # LOW = capteur déclenché (faisceau coupé)
        return GPIO.input(self.limit_forward_pin) == GPIO.LOW

    def _is_limit_backward_triggered(self):
        """Vérifie si le capteur de fin de course arrière est déclenché."""
        if not self.enabled:
            return False
        # LOW = capteur déclenché (faisceau coupé)
        return GPIO.input(self.limit_backward_pin) == GPIO.LOW

    def _set_direction(self, fwd, bwd):
        GPIO.output(self.forward_pin, fwd)
        GPIO.output(self.backward_pin, bwd)
        self._current_fwd = fwd
        self._current_bwd = bwd

    def _ramp_up(self):
        """Increase duty cycle to 100 %, stopping early if cancelled or limit reached."""
        step = max(1, int((100 - self._duty) / self.RAMP_STEPS))
        duty = self._duty
        while duty < 100 and not self._cancel.is_set():
            # Vérifier les capteurs de fin de course pendant la rampe
            if self._current_fwd and self._is_limit_forward_triggered():
                print("Capteur de fin de course avant déclenché - arrêt")
                self._cancel.set()
                break
            if self._current_bwd and self._is_limit_backward_triggered():
                print("Capteur de fin de course arrière déclenché - arrêt")
                self._cancel.set()
                break
            
            duty = min(duty + step, 100)
            self._pwm.ChangeDutyCycle(duty)
            self._duty = duty
            time.sleep(self.RAMP_STEP_DELAY)

    def _ramp_down(self):
        """Decrease duty cycle to 0 %, stopping early if cancelled."""
        step = max(1, int(self._duty / self.RAMP_STEPS))
        duty = self._duty
        while duty > 0 and not self._cancel.is_set():
            duty = max(duty - step, 0)
            self._pwm.ChangeDutyCycle(duty)
            self._duty = duty
            time.sleep(self.RAMP_STEP_DELAY)

    def _execute(self, fwd, bwd, do_move):
        """
        Interrupt any running ramp, acquire the lock, then:
          1. Check if already moving in the requested direction
          2. If not, ramp down to 0
          3. Switch direction
          4. Ramp up (if do_move=True)
        """
        self._cancel.set()          # interrupt running ramp immediately
        with self._lock:
            self._cancel.clear()    # we now own the motor
            
            # Check if already moving in the requested direction at full speed
            if do_move and fwd == self._current_fwd and bwd == self._current_bwd and self._duty == 100:
                # Already at full speed in the correct direction, nothing to do
                return
            
            self._ramp_down()
            if self._cancel.is_set():
                return              # superseded by yet another command
            self._set_direction(fwd, bwd)
            if do_move:
                self._ramp_up()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def move_forward(self):
        """Démarrer le déplacement vers l'avant avec accélération progressive."""
        if not self.enabled:
            raise RuntimeError('GPIO non disponible')
        # Vérifier si le capteur de fin de course avant est déjà déclenché
        if self._is_limit_forward_triggered():
            print("Capteur de fin de course avant déjà déclenché - mouvement impossible")
            return
        self._execute(GPIO.HIGH, GPIO.LOW, do_move=True)

    def move_backward(self):
        """Démarrer le déplacement vers l'arrière avec accélération progressive."""
        if not self.enabled:
            raise RuntimeError('GPIO non disponible')
        # Vérifier si le capteur de fin de course arrière est déjà déclenché
        if self._is_limit_backward_triggered():
            print("Capteur de fin de course arrière déjà déclenché - mouvement impossible")
            return
        self._execute(GPIO.LOW, GPIO.HIGH, do_move=True)

    def stop(self):
        """Arrêter le moteur avec décélération progressive."""
        if not self.enabled:
            return
        self._execute(GPIO.LOW, GPIO.LOW, do_move=False)

    def calibrate(self):
        """
        Calibrer la position de référence du rail.
        Déplace le moteur vers l'arrière jusqu'à atteindre le capteur de fin de course.
        """
        if not self.enabled:
            raise RuntimeError('GPIO non disponible')
        
        print("Début de la calibration...")
        
        # Si déjà sur le capteur arrière, avancer légèrement
        if self._is_limit_backward_triggered():
            print("Déjà sur le capteur arrière, recul de quelques secondes")
            self.move_forward()
            time.sleep(2)
            self.stop()
            time.sleep(0.5)
        
        # Déplacement vers l'arrière jusqu'au capteur
        print("Déplacement vers la position de référence...")
        self.move_backward()
        
        # Attendre que le capteur soit déclenché (max 30 secondes)
        start_time = time.time()
        while not self._is_limit_backward_triggered() and (time.time() - start_time) < 30:
            time.sleep(0.1)
        
        self.stop()
        
        if self._is_limit_backward_triggered():
            print("Calibration terminée - position de référence atteinte")
            # Réinitialiser la position de l'encodeur à la position de référence
            self.reset_encoder_position()
            print("Position de l'encodeur réinitialisée à zéro")
            return {'success': True, 'message': 'Position de référence atteinte'}
        else:
            print("Calibration échouée - timeout")
            return {'success': False, 'message': 'Timeout - capteur non atteint'}

    def cleanup(self):
        """Libérer les GPIO."""
        if not self.enabled:
            return
        self.stop()
        if self._pwm:
            self._pwm.stop()
            self._pwm = None  # Prevent double cleanup in __del__
        GPIO.cleanup()
        self.enabled = False

    def is_available(self):
        return self.enabled

    def check_gpio(self):
        """Vérifie si les GPIO ont été initialisés correctement."""
        return self.is_available()

    def get_limit_switches_status(self):
        """Retourne l'état des capteurs de fin de course."""
        if not self.enabled:
            return {'forward': False, 'backward': False, 'available': False}
        return {
            'forward': self._is_limit_forward_triggered(),
            'backward': self._is_limit_backward_triggered(),
            'available': True
        }

    def can_move_forward(self):
        """Vérifie si le mouvement vers l'avant est possible."""
        return self.enabled and not self._is_limit_forward_triggered()

    def can_move_backward(self):
        """Vérifie si le mouvement vers l'arrière est possible."""
        return self.enabled and not self._is_limit_backward_triggered()

    # ------------------------------------------------------------------
    # Encoder / Position tracking methods
    # ------------------------------------------------------------------

    def get_encoder_position(self):
        """
        Retourne la position actuelle de l'encodeur en impulsions.
        Valeur positive = déplacement vers l'avant, négative = vers l'arrière.
        """
        with self._encoder_lock:
            return self._encoder_position

    def get_encoder_distance(self):
        """
        Retourne la distance actuelle depuis la position de référence (en mm).
        """
        position = self.get_encoder_position()
        return position * self.MM_PER_PULSE

    def get_total_distance_traveled(self):
        """
        Retourne la distance totale parcourue depuis le démarrage (en mm).
        Cette valeur est toujours positive et cumulative.
        """
        with self._encoder_lock:
            return self._encoder_total_pulses * self.MM_PER_PULSE

    def get_session_distance_traveled(self):
        """
        Retourne la distance parcourue depuis le démarrage de la session (en mm).
        """
        with self._encoder_lock:
            return self._encoder_session_pulses * self.MM_PER_PULSE

    def reset_encoder_position(self):
        """
        Réinitialise la position de l'encodeur à zéro (position de référence).
        Ne réinitialise pas les compteurs de distance totale et de session.
        """
        with self._encoder_lock:
            self._encoder_position = 0

    def reset_session_distance(self):
        """
        Réinitialise le compteur de distance de la session.
        """
        with self._encoder_lock:
            self._encoder_session_pulses = 0

    def get_encoder_stats(self):
        """
        Retourne un dictionnaire avec toutes les statistiques de l'encodeur.
        """
        with self._encoder_lock:
            return {
                'position_pulses': self._encoder_position,
                'position_mm': self._encoder_position * self.MM_PER_PULSE,
                'total_distance_mm': self._encoder_total_pulses * self.MM_PER_PULSE,
                'session_distance_mm': self._encoder_session_pulses * self.MM_PER_PULSE,
                'total_pulses': self._encoder_total_pulses,
                'session_pulses': self._encoder_session_pulses,
                'mm_per_pulse': self.MM_PER_PULSE
            }

    def set_mm_per_pulse(self, mm_per_pulse):
        """
        Configure la distance par impulsion (calibration mécanique).
        À calculer selon : (circonférence de la poulie en mm) / (impulsions par tour)
        """
        if mm_per_pulse > 0:
            self.MM_PER_PULSE = mm_per_pulse
            return True
        return False

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
