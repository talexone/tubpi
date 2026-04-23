#!/usr/bin/env python3
"""Script de test pour l'encodeur de position."""

import time
import sys
from motor_driver import MotorDriver

def test_encoder():
    """Test interactif de l'encodeur."""
    print("=== Test de l'encodeur de position ===\n")
    
    # Option pour tester sans l'encodeur (diagnostic)
    enable_encoder = True
    if len(sys.argv) > 1 and sys.argv[1] == '--no-encoder':
        enable_encoder = False
        print("Mode diagnostic : encodeur DÉSACTIVÉ\n")
    
    # Initialiser le driver
    print("Initialisation du driver moteur avec encodeur...")
    driver = MotorDriver(enable_encoder=enable_encoder)
    
    if not driver.is_available():
        print("ERREUR : GPIO non disponible")
        print("Vérifiez que vous êtes sur un Raspberry Pi avec les permissions GPIO")
        return 1
    
    print("Driver initialisé avec succès\n")
    
    try:
        if not enable_encoder:
            print("⚠️  L'encodeur est désactivé - test de mouvement uniquement ⚠️\n")
            # Test simple de mouvement
            print("Test de mouvement (3 secondes avant, 3 secondes arrière)...")
            print("\nAvancement pendant 3 secondes...")
            driver.move_forward()
            time.sleep(3)
            driver.stop()
            time.sleep(0.5)
            
            print("Recul pendant 3 secondes...")
            driver.move_backward()
            time.sleep(3)
            driver.stop()
            
            print("\n✅ Test de mouvement terminé (durée correcte sans encodeur)")
            return 0
        
        # Test 1 : Affichage de la configuration
        print("--- Test 1 : Configuration de l'encodeur ---")
        stats = driver.get_encoder_stats()
        print(f"Distance par impulsion : {stats['mm_per_pulse']} mm")
        print(f"Position initiale : {stats['position_pulses']} impulsions ({stats['position_mm']:.2f} mm)")
        print()
        
        # Test 2 : Surveillance en temps réel
        print("--- Test 2 : Surveillance en temps réel (30 secondes) ---")
        print("Déplacez le moteur manuellement ou via commande pour voir les changements...")
        print("Appuyez sur Ctrl+C pour arrêter\n")
        print("Format: [Temps] Position: XXX imp (XX.XX mm) | Session: XX.XX mm | Total: XX.XX mm\n")
        
        start_time = time.time()
        last_position = None
        
        while (time.time() - start_time) < 30:
            stats = driver.get_encoder_stats()
            current_position = stats['position_pulses']
            
            # Afficher seulement si la position change
            if current_position != last_position:
                print(f"[{time.strftime('%H:%M:%S')}] "
                      f"Position: {stats['position_pulses']:6d} imp ({stats['position_mm']:8.2f} mm) | "
                      f"Session: {stats['session_distance_mm']:8.2f} mm | "
                      f"Total: {stats['total_distance_mm']:8.2f} mm")
                last_position = current_position
            
            time.sleep(0.05)  # 20 Hz
        
        print("\n--- Test 3 : Statistiques finales ---")
        stats = driver.get_encoder_stats()
        print(f"Position finale      : {stats['position_pulses']} impulsions ({stats['position_mm']:.2f} mm)")
        print(f"Distance de session  : {stats['session_distance_mm']:.2f} mm ({stats['session_pulses']} impulsions)")
        print(f"Distance totale      : {stats['total_distance_mm']:.2f} mm ({stats['total_pulses']} impulsions)")
        print()
        
        # Test 4 : Test de mouvement avec suivi
        print("--- Test 4 : Test de mouvement avec suivi de position ---")
        response = input("Lancer un test de mouvement ? (o/n) : ")
        if response.lower() == 'o':
            print("\nPosition avant mouvement:")
            start_stats = driver.get_encoder_stats()
            print(f"  Position: {start_stats['position_mm']:.2f} mm")
            
            print("\nAvancement pendant 3 secondes...")
            driver.move_forward()
            time.sleep(3)
            driver.stop()
            time.sleep(0.5)
            
            mid_stats = driver.get_encoder_stats()
            print(f"  Position après avancement: {mid_stats['position_mm']:.2f} mm")
            print(f"  Distance parcourue: {mid_stats['position_mm'] - start_stats['position_mm']:.2f} mm")
            
            print("\nRecul pendant 3 secondes...")
            driver.move_backward()
            time.sleep(3)
            driver.stop()
            time.sleep(0.5)
            
            end_stats = driver.get_encoder_stats()
            print(f"  Position finale: {end_stats['position_mm']:.2f} mm")
            print(f"  Distance nette: {end_stats['position_mm'] - start_stats['position_mm']:.2f} mm")
            print(f"  Distance totale parcourue: {end_stats['total_distance_mm'] - start_stats['total_distance_mm']:.2f} mm")
        
        # Test 5 : Réinitialisation
        print("\n--- Test 5 : Réinitialisation de la position ---")
        response = input("Réinitialiser la position à zéro ? (o/n) : ")
        if response.lower() == 'o':
            before_pos = driver.get_encoder_position()
            driver.reset_encoder_position()
            after_pos = driver.get_encoder_position()
            print(f"Position avant : {before_pos} impulsions")
            print(f"Position après : {after_pos} impulsions")
        
        # Test 6 : Calibration mécanique
        print("\n--- Test 6 : Calibration mécanique (mm par impulsion) ---")
        print(f"Valeur actuelle : {driver.MM_PER_PULSE} mm/impulsion")
        response = input("Modifier cette valeur ? (o/n) : ")
        if response.lower() == 'o':
            try:
                new_value = float(input("Nouvelle valeur (mm/impulsion) : "))
                if driver.set_mm_per_pulse(new_value):
                    print(f"Valeur mise à jour : {driver.MM_PER_PULSE} mm/impulsion")
                else:
                    print("ERREUR : la valeur doit être positive")
            except ValueError:
                print("ERREUR : valeur invalide")
        
        print("\n=== Tests terminés avec succès ===")
        return 0
        
    except KeyboardInterrupt:
        print("\n\nInterruption par l'utilisateur")
        return 0
    except Exception as e:
        print(f"\nERREUR : {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        print("\nNettoyage des GPIO...")
        driver.cleanup()
        print("Terminé")

if __name__ == '__main__':
    sys.exit(test_encoder())
