#!/usr/bin/env python3
"""Script de test pour les capteurs de fin de course."""

import time
import sys
from motor_driver import MotorDriver

def test_limit_switches():
    """Test interactif des capteurs de fin de course."""
    print("=== Test des capteurs de fin de course ===\n")
    
    # Initialiser le driver
    print("Initialisation du driver moteur...")
    driver = MotorDriver()
    
    if not driver.is_available():
        print("ERREUR : GPIO non disponible")
        print("Vérifiez que vous êtes sur un Raspberry Pi avec les permissions GPIO")
        return 1
    
    print("Driver initialisé avec succès\n")
    
    try:
        # Test 1 : Lecture de l'état des capteurs
        print("--- Test 1 : État des capteurs ---")
        status = driver.get_limit_switches_status()
        print(f"Capteur avant (forward)  : {'DÉCLENCHÉ' if status['forward'] else 'LIBRE'}")
        print(f"Capteur arrière (backward): {'DÉCLENCHÉ' if status['backward'] else 'LIBRE'}")
        print()
        
        # Test 2 : Surveillance continue
        print("--- Test 2 : Surveillance continue (10 secondes) ---")
        print("Déclenchez les capteurs pour voir le changement d'état...")
        print("Appuyez sur Ctrl+C pour arrêter\n")
        
        start_time = time.time()
        last_status = {'forward': None, 'backward': None}
        
        while (time.time() - start_time) < 10:
            current_status = driver.get_limit_switches_status()
            
            # Afficher seulement si l'état change
            if (current_status['forward'] != last_status['forward'] or 
                current_status['backward'] != last_status['backward']):
                
                print(f"[{time.strftime('%H:%M:%S')}] ", end='')
                if current_status['forward'] != last_status['forward']:
                    state = "DÉCLENCHÉ" if current_status['forward'] else "LIBRE"
                    print(f"Avant: {state} ", end='')
                if current_status['backward'] != last_status['backward']:
                    state = "DÉCLENCHÉ" if current_status['backward'] else "LIBRE"
                    print(f"Arrière: {state}", end='')
                print()
                
                last_status = current_status
            
            time.sleep(0.1)
        
        print("\n--- Test 3 : Vérification des mouvements possibles ---")
        print(f"Peut avancer : {'OUI' if driver.can_move_forward() else 'NON'}")
        print(f"Peut reculer : {'OUI' if driver.can_move_backward() else 'NON'}")
        print()
        
        # Test 4 : Calibration (optionnel)
        print("--- Test 4 : Calibration ---")
        response = input("Lancer la calibration ? (o/n) : ")
        if response.lower() == 'o':
            print("Lancement de la calibration...")
            result = driver.calibrate()
            print(f"Résultat : {result}")
        
        print("\n=== Tests terminés avec succès ===")
        return 0
        
    except KeyboardInterrupt:
        print("\n\nInterruption par l'utilisateur")
        return 0
    except Exception as e:
        print(f"\nERREUR : {e}")
        return 1
    finally:
        print("\nNettoyage des GPIO...")
        driver.cleanup()
        print("Terminé")

if __name__ == '__main__':
    sys.exit(test_limit_switches())
