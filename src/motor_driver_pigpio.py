"""Pilote du moteur pour le déplacement de la caméra sur rail - Version pigpio.

Cette version utilise pigpio pour une meilleure performance et compatibilité avec tous
les modèles de Raspberry Pi (incluant Pi 5).

Avantages de pigpio:
- Compatible Pi 1, 2, 3, 4, 5
- PWM matériel très précis (jusqu'à 40kHz)
- Callbacks optimisés avec timing précis
- Meilleure gestion des interruptions encodeur
- Pas de problème de permissions /dev/mem
"""

import sys
import time
import threading
import pigpio

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
                 limit_forward_pin=23, limit_backward_pin=24,
                 encoder_a_pin=17, encoder_b_pin=27, encoder_index_pin=22,
                 enable_encoder=True):
        print("Initialisation pigpio...")
        self.forward_pin = forward_pin
        self.backward_pin = backward_pin
        self._pwm_pin = pwm_pin
        # GPIO 23 : capteur devant (forward) - se déclenche en premier lors du mouvement vers l'avant
        # GPIO 24 : capteur reculé (backward) - se déclenche en premier lors du mouvement vers l'arrière
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
        
        # Callbacks pigpio
        self._cb_encoder_a = None
        self._cb_encoder_b = None
        
        self._duty = 0          # current duty cycle (0-100)
        self._current_fwd = False   # current forward pin state
        self._current_bwd = False   # current backward pin state
        self._lock = threading.Lock()   # serializes commands
        self._cancel = threading.Event()  # signals ramp loops to stop early
        self.enabled = False
        
        # Connexion au daemon pigpio
        self.pi = pigpio.pi()
        
        if not self.pi.connected:
            print("ERREUR: Impossible de se connecter au daemon pigpio")
            print("Assurez-vous que pigpiod est démarré: sudo systemctl start pigpiod")
            self.enabled = False
            return

        try:
            # Configuration des GPIO en sortie
            self.pi.set_mode(self.forward_pin, pigpio.OUTPUT)
            self.pi.set_mode(self.backward_pin, pigpio.OUTPUT)
            self.pi.set_mode(self._pwm_pin, pigpio.OUTPUT)
            
            # Configuration des capteurs de fin de course en entrée avec pull-up
            # Pull-up : HIGH quand libre, LOW quand déclenché
            self.pi.set_mode(self.limit_forward_pin, pigpio.INPUT)
            self.pi.set_pull_up_down(self.limit_forward_pin, pigpio.PUD_UP)
            self.pi.set_mode(self.limit_backward_pin, pigpio.INPUT)
            self.pi.set_pull_up_down(self.limit_backward_pin, pigpio.PUD_UP)
            
            # Configuration de l'encodeur (optionnel)
            if self.encoder_enabled:
                # Les signaux viennent du Level Shifter (5V -> 3.3V)
                self.pi.set_mode(self.encoder_a_pin, pigpio.INPUT)
                self.pi.set_pull_up_down(self.encoder_a_pin, pigpio.PUD_UP)
                self.pi.set_mode(self.encoder_b_pin, pigpio.INPUT)
                self.pi.set_pull_up_down(self.encoder_b_pin, pigpio.PUD_UP)
                self.pi.set_mode(self.encoder_index_pin, pigpio.INPUT)
                self.pi.set_pull_up_down(self.encoder_index_pin, pigpio.PUD_UP)
                
                # Lire l'état initial de l'encodeur
                self._encoder_last_a = self.pi.read(self.encoder_a_pin)
                self._encoder_last_b = self.pi.read(self.encoder_b_pin)
                
                # Configurer les callbacks sur les canaux A et B
                # pigpio supporte nativement le debouncing et est très efficace
                self._cb_encoder_a = self.pi.callback(
                    self.encoder_a_pin, 
                    pigpio.EITHER_EDGE, 
                    self._encoder_callback
                )
                self._cb_encoder_b = self.pi.callback(
                    self.encoder_b_pin, 
                    pigpio.EITHER_EDGE, 
                    self._encoder_callback
                )
                print("Encodeur activé avec callbacks pigpio")
            else:
                print("Encodeur désactivé")

            # Initialiser le PWM matériel
            # pigpio permet un PWM très précis avec fréquence variable
            self.pi.set_PWM_frequency(self._pwm_pin, self.PWM_FREQ)
            self.pi.set_PWM_range(self._pwm_pin, 100)  # Range 0-100 pour correspondre au %
            self.pi.set_PWM_dutycycle(self._pwm_pin, 0)

            # État initial : moteur arrêté
            self.pi.write(self.forward_pin, 0)
            self.pi.write(self.backward_pin, 0)
            self._current_fwd = 0
            self._current_bwd = 0
            self.enabled = True
            print("Motor driver initialisé avec pigpio")
        except Exception as exc:
            print(f"Impossible d'initialiser les GPIO avec pigpio : {exc}")
            self.pi.stop()
            self.enabled = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encoder_callback(self, gpio, level, tick):
        """
        Callback pour les interruptions de l'encodeur en quadrature.
        Détermine la direction et met à jour les compteurs.
        
        Args:
            gpio: numéro du GPIO qui a déclenché le callback
            level: 0 ou 1 (état du GPIO)
            tick: timestamp en microsecondes
        """
        if not self.encoder_enabled:
            return
        
        # Utiliser trylock pour ne pas bloquer si occupé
        if not self._encoder_lock.acquire(blocking=False):
            return  # Skip this interrupt if we can't get the lock immediately
        
        try:
            # Lire l'état actuel des deux canaux
            a = self.pi.read(self.encoder_a_pin)
            b = self.pi.read(self.encoder_b_pin)
            
            # Déterminer la direction en comparant l'état actuel avec le précédent
            # Encodeur en quadrature : quand A change, si B=0 on avance, si B=1 on recule
            # Quand B change, si A=1 on avance, si A=0 on recule
            if gpio == self.encoder_a_pin and a != self._encoder_last_a:
                if a == b:
                    # Rotation inverse (backward)
                    self._encoder_position -= 1
                else:
                    # Rotation avant (forward)
                    self._encoder_position += 1
                self._encoder_total_pulses += 1
                self._encoder_session_pulses += 1
                self._encoder_last_a = a
            elif gpio == self.encoder_b_pin and b != self._encoder_last_b:
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
        return self.pi.read(self.limit_forward_pin) == 0

    def _is_limit_backward_triggered(self):
        """Vérifie si le capteur de fin de course arrière est déclenché."""
        if not self.enabled:
            return False
        # LOW = capteur déclenché (faisceau coupé)
        return self.pi.read(self.limit_backward_pin) == 0

    def _set_direction(self, fwd, bwd):
        """Configure la direction du moteur."""
        self.pi.write(self.forward_pin, fwd)
        self.pi.write(self.backward_pin, bwd)
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
            self.pi.set_PWM_dutycycle(self._pwm_pin, duty)
            self._duty = duty
            time.sleep(self.RAMP_STEP_DELAY)

    def _ramp_down(self):
        """Decrease duty cycle to 0 %, stopping early if cancelled."""
        step = max(1, int(self._duty / self.RAMP_STEPS))
        duty = self._duty
        while duty > 0 and not self._cancel.is_set():
            duty = max(duty - step, 0)
            self.pi.set_PWM_dutycycle(self._pwm_pin, duty)
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
        # Vérifier les capteurs AVANT de commencer le mouvement
        if do_move:
            if fwd and self._is_limit_forward_triggered():
                print("Impossible de démarrer : capteur de fin de course avant déjà déclenché")
                return
            if bwd and self._is_limit_backward_triggered():
                print("Impossible de démarrer : capteur de fin de course arrière déjà déclenché")
                return
        
        self._cancel.set()  # stop any ongoing ramp
        with self._lock:
            self._cancel.clear()
            # 1. Already going the right direction?
            if fwd == self._current_fwd and bwd == self._current_bwd:
                if do_move and self._duty == 100:
                    return  # already at full speed
                elif not do_move and self._duty == 0:
                    return  # already stopped
            # 2. Ramp down if we were moving
            if self._duty > 0:
                self._ramp_down()
            # 3. Switch direction
            self._set_direction(fwd, bwd)
            # 4. Ramp up if needed
            if do_move:
                self._ramp_up()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def move_forward(self):
        """Start moving forward (with ramp-up)."""
        if not self.enabled:
            print("Motor driver non disponible")
            return
        print("Move forward")
        self._execute(fwd=1, bwd=0, do_move=True)

    def move_backward(self):
        """Start moving backward (with ramp-up)."""
        if not self.enabled:
            print("Motor driver non disponible")
            return
        print("Move backward")
        self._execute(fwd=0, bwd=1, do_move=True)

    def stop(self):
        """Stop the motor (with ramp-down)."""
        if not self.enabled:
            return
        print("Stop")
        self._execute(fwd=0, bwd=0, do_move=False)

    def calibrate(self):
        """
        Calibration automatique : déplace le moteur vers l'arrière jusqu'à ce que
        le capteur de fin de course arrière soit déclenché, puis réinitialise la position.
        """
        if not self.enabled:
            print("Motor driver non disponible")
            return False
        
        print("=== Calibration automatique ===")
        print("Déplacement vers la position de référence (capteur arrière)...")
        
        # Si déjà au capteur arrière, reculer un peu d'abord
        if self._is_limit_backward_triggered():
            print("Déjà au capteur arrière, recul de 0.5s pour réinitialiser")
            self.move_forward()
            time.sleep(0.5)
            self.stop()
            time.sleep(0.2)
        
        # Démarrer le mouvement vers l'arrière
        self.move_backward()
        
        # Attendre que le capteur soit déclenché (avec timeout de sécurité)
        timeout = 30  # secondes
        start_time = time.time()
        while not self._is_limit_backward_triggered():
            if time.time() - start_time > timeout:
                print("TIMEOUT: Calibration échouée - capteur arrière non atteint")
                self.stop()
                return False
            time.sleep(0.05)
        
        # Capteur déclenché, arrêter immédiatement
        self.stop()
        time.sleep(0.2)
        
        # Réinitialiser la position de l'encodeur à 0
        with self._encoder_lock:
            self._encoder_position = 0
        
        print(f"✓ Calibration terminée - Position réinitialisée à 0")
        print(f"  Distance de session avant calibration: {self.get_encoder_stats()['session_distance_mm']:.1f} mm")
        return True

    def get_encoder_stats(self):
        """
        Retourne les statistiques de l'encodeur.
        
        Returns:
            dict avec les clés:
                - position_pulses: position actuelle en impulsions (peut être négatif)
                - position_mm: position actuelle en mm
                - session_distance_mm: distance parcourue depuis le démarrage
                - total_distance_mm: distance totale cumulée
        """
        if not self.enabled or not self.encoder_enabled:
            return {
                'position_pulses': 0,
                'position_mm': 0.0,
                'session_distance_mm': 0.0,
                'total_distance_mm': 0.0,
                'available': False
            }
        
        with self._encoder_lock:
            return {
                'position_pulses': self._encoder_position,
                'position_mm': self._encoder_position * self.MM_PER_PULSE,
                'session_distance_mm': self._encoder_session_pulses * self.MM_PER_PULSE,
                'total_distance_mm': self._encoder_total_pulses * self.MM_PER_PULSE,
                'available': True
            }

    def reset_encoder_position(self):
        """Réinitialise la position de l'encodeur à 0 (sans affecter les distances totales)."""
        if not self.enabled or not self.encoder_enabled:
            return
        with self._encoder_lock:
            self._encoder_position = 0
        print("Position de l'encodeur réinitialisée à 0")

    def cleanup(self):
        """Clean up pigpio resources."""
        if not self.enabled:
            return
        
        print("Nettoyage pigpio...")
        
        # Arrêter le moteur
        self.stop()
        time.sleep(0.3)
        
        # Désactiver les callbacks encodeur
        if self._cb_encoder_a:
            self._cb_encoder_a.cancel()
        if self._cb_encoder_b:
            self._cb_encoder_b.cancel()
        
        # Arrêter le PWM
        self.pi.set_PWM_dutycycle(self._pwm_pin, 0)
        
        # Fermer la connexion pigpio
        self.pi.stop()
        self.enabled = False

    def is_available(self):
        """Retourne True si le driver est disponible."""
        return self.enabled and self.pi.connected

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


# ------------------------------------------------------------------
# Test code
# ------------------------------------------------------------------

if __name__ == '__main__':
    import signal
    
    def signal_handler(sig, frame):
        print('\nInterruption détectée, arrêt...')
        motor.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    motor = MotorDriver()
    
    if not motor.is_available():
        print("ERREUR: Motor driver non disponible")
        print("\nAssurez-vous que:")
        print("1. Le daemon pigpiod est démarré: sudo systemctl start pigpiod")
        print("2. L'utilisateur a les permissions GPIO (groupe 'gpio')")
        sys.exit(1)
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        print("\n=== Test automatique du moteur ===")
        print("Test 1: Avancer 3 secondes")
        motor.move_forward()
        time.sleep(3)
        
        print("\nTest 2: Arrêt")
        motor.stop()
        time.sleep(1)
        
        print("\nTest 3: Reculer 3 secondes")
        motor.move_backward()
        time.sleep(3)
        
        print("\nTest 4: Arrêt final")
        motor.stop()
        
        if motor.encoder_enabled:
            stats = motor.get_encoder_stats()
            print("\n=== Statistiques encodeur ===")
            print(f"Position: {stats['position_mm']:.1f} mm ({stats['position_pulses']} impulsions)")
            print(f"Distance session: {stats['session_distance_mm']:.1f} mm")
            print(f"Distance totale: {stats['total_distance_mm']:.1f} mm")
        
        motor.cleanup()
    else:
        print("\nCommandes disponibles:")
        print("  f = forward")
        print("  b = backward")
        print("  s = stop")
        print("  c = calibrate")
        print("  e = encoder stats")
        print("  r = reset encoder position")
        print("  l = limit switches status")
        print("  q = quit")
        
        try:
            while True:
                cmd = input("\nCommande: ").strip().lower()
                if cmd == 'f':
                    motor.move_forward()
                elif cmd == 'b':
                    motor.move_backward()
                elif cmd == 's':
                    motor.stop()
                elif cmd == 'c':
                    motor.calibrate()
                elif cmd == 'e':
                    stats = motor.get_encoder_stats()
                    if stats['available']:
                        print(f"Position: {stats['position_mm']:.1f} mm ({stats['position_pulses']} impulsions)")
                        print(f"Distance session: {stats['session_distance_mm']:.1f} mm")
                        print(f"Distance totale: {stats['total_distance_mm']:.1f} mm")
                    else:
                        print("Encodeur non disponible")
                elif cmd == 'r':
                    motor.reset_encoder_position()
                elif cmd == 'l':
                    status = motor.get_limit_switches_status()
                    if status['available']:
                        print(f"Capteur avant (forward): {'DÉCLENCHÉ' if status['forward'] else 'libre'}")
                        print(f"Capteur arrière (backward): {'DÉCLENCHÉ' if status['backward'] else 'libre'}")
                    else:
                        print("Capteurs non disponibles")
                elif cmd == 'q':
                    break
        finally:
            motor.cleanup()
