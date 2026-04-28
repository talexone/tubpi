"""Pilote moteur simplifié sans rampe, capteurs ni PWM pour les tests."""

import sys
import RPi.GPIO as GPIO

class SimpleMotorDriver:
    """Version simplifiée du pilote moteur pour les tests.
    
    - Pas de rampe d'accélération
    - Pas de capteurs de fin de course
    - Pas d'encodeur
    - Pas de PWM (vitesse fixe 100%)
    - Contrôle direct marche/arrêt uniquement
    """

    def __init__(self, forward_pin=20, backward_pin=21, motor_enabled_pin=26):
        """Initialise le pilote moteur simplifié.
        
        Args:
            forward_pin: GPIO pour direction avant
            backward_pin: GPIO pour direction arrière
        """
        print("Initialisation du pilote moteur simplifié (sans PWM)")
        self.forward_pin = forward_pin
        self.backward_pin = backward_pin
        self.motor_enabled_pin = motor_enabled_pin
        self.enabled = False
        self._current_direction = 'stop'  # 'forward', 'backward', 'stop'

        try:
            GPIO.setmode(GPIO.BCM)
            # Initialiser les pins avec état LOW            
            GPIO.setup(self.forward_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.backward_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.motor_enabled_pin, GPIO.OUT, initial=GPIO.HIGH)

            GPIO.output(self.forward_pin, GPIO.LOW)
            GPIO.output(self.backward_pin, GPIO.LOW)
            
            self.enabled = True
            print("Pilote moteur simplifié initialisé (vitesse fixe 100%)")
        except RuntimeError as exc:
            print(f"Impossible d'initialiser les GPIO : {exc}")
            self.enabled = False

    def forward(self):
        """Démarre le moteur en avant à pleine vitesse."""
        if not self.enabled:
            print("GPIO non disponible")
            return False
        
        print("Moteur AVANT (100%)")
        GPIO.output(self.forward_pin, GPIO.HIGH)
        GPIO.output(self.backward_pin, GPIO.LOW)
        self._current_direction = 'forward'
        return True

    def backward(self):
        """Démarre le moteur en arrière à pleine vitesse."""
        if not self.enabled:
            print("GPIO non disponible")
            return False
        
        print("Moteur ARRIÈRE (100%)")
        GPIO.output(self.forward_pin, GPIO.LOW)
        GPIO.output(self.backward_pin, GPIO.HIGH)
        self._current_direction = 'backward'
        return True

    def stop(self):
        """Arrête le moteur immédiatement."""
        if not self.enabled:
            return False
        
        print("Moteur STOP")
        GPIO.output(self.forward_pin, GPIO.LOW)
        GPIO.output(self.backward_pin, GPIO.LOW)
        self._current_direction = 'stop'
        return True

    def get_status(self):
        """Retourne l'état actuel du moteur."""
        return {
            'enabled': self.enabled,
            'direction': self._current_direction
        }

    def cleanup(self):
        """Libère les GPIO."""
        if not self.enabled:
            return
        
        self.stop()
        GPIO.cleanup()
        self.enabled = False
        print("GPIO nettoyés")

    def __del__(self):
        """Destructeur pour nettoyer les GPIO."""
        self.cleanup()

    def is_available(self):
        """Vérifie si le moteur est disponible."""
        return self.enabled


# Script de test simple
if __name__ == '__main__':
    import time
    
    print("\n=== Test du pilote moteur simplifié (sans PWM) ===\n")
    
    motor = SimpleMotorDriver()
    
    if not motor.is_available():
        print("Erreur: GPIO non disponible")
        sys.exit(1)
    
    try:
        print("\n1. Test avant pendant 5 secondes...")
        motor.forward()
        time.sleep(5)
        motor.stop()
        time.sleep(1)
        
        print("\n2. Test arrière pendant 5 secondes...")
        motor.backward()
        time.sleep(5)
        motor.stop()
        time.sleep(1)
        
        print("\n3. Test avant pendant 5 secondes...")
        motor.forward()
        time.sleep(5)
        motor.stop()
        time.sleep(1)
        
        print("\n4. Test arrière pendant 5 secondes...")
        motor.backward()
        time.sleep(5)
        motor.stop()
        time.sleep(1)
        
        print("\n5. Test séquence rapide...")
        motor.forward()
        time.sleep(0.5)
        motor.stop()
        time.sleep(0.5)
        motor.backward()
        time.sleep(0.5)
        motor.stop()
        time.sleep(0.5)
        motor.forward()
        time.sleep(0.5)
        motor.stop()
        
        print("\n=== Tests terminés avec succès ===")
        
    except KeyboardInterrupt:
        print("\n\nInterrompu par l'utilisateur")
    finally:
        motor.cleanup()
        print("Nettoyage terminé")
