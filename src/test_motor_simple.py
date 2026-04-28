#!/usr/bin/env python3
"""Script interactif pour tester le moteur avec le pilote simplifié."""

import sys
import time
from motor_driver_simple import SimpleMotorDriver

def print_menu():
    """Affiche le menu des commandes."""
    print("\n" + "="*50)
    print("   TEST MOTEUR SIMPLIFIÉ (sans PWM, rampe ni capteurs)")
    print("="*50)
    print("\nCommandes disponibles:")
    print("  f  - Avancer (100%)")
    print("  b  - Reculer (100%)")
    print("  s  - Stop")
    print("  i  - Afficher infos moteur")
    print("  t  - Lancer test automatique")
    print("  q  - Quitter")
    print("="*50)

def run_automatic_test(motor):
    """Lance une séquence de test automatique."""
    print("\n🔄 Démarrage du test automatique...\n")
    
    tests = [
        ("Avant", lambda: motor.forward(), 2),
        ("Stop", lambda: motor.stop(), 1),
        ("Arrière", lambda: motor.backward(), 2),
        ("Stop", lambda: motor.stop(), 1),
        ("Avant", lambda: motor.forward(), 1.5),
        ("Stop", lambda: motor.stop(), 0.5),
        ("Arrière", lambda: motor.backward(), 1.5),
        ("Stop", lambda: motor.stop(), 0.5),
        ("Avant rapide", lambda: motor.forward(), 0.5),
        ("Stop", lambda: motor.stop(), 0.3),
        ("Arrière rapide", lambda: motor.backward(), 0.5),
        ("Stop", lambda: motor.stop(), 0.5),
    ]
    
    try:
        for i, (description, action, duration) in enumerate(tests, 1):
            print(f"[{i}/{len(tests)}] {description}...")
            action()
            time.sleep(duration)
        
        print("\n✅ Test automatique terminé avec succès!\n")
    except KeyboardInterrupt:
        print("\n⚠️  Test interrompu par l'utilisateur")
        motor.stop()



def main():
    """Fonction principale."""
    print("\n🔧 Initialisation du moteur simplifié...\n")
    
    # Créer le moteur sans PWM
    motor = SimpleMotorDriver()
    
    if not motor.is_available():
        print("❌ Erreur: GPIO non disponible")
        print("   Assurez-vous d'exécuter ce script en tant que root:")
        print("   sudo python3 test_motor_simple.py")
        sys.exit(1)
    
    print("✅ Moteur initialisé avec succès\n")
    print_menu()
    
    try:
        while True:
            try:
                # Lire la commande
                cmd = input("\n> ").strip().lower()
                
                if not cmd:
                    continue
                
                # Parser la commande
                parts = cmd.split()
                command = parts[0]
                
                if command in ('q', 'quit', 'exit'):
                    print("\n👋 Arrêt du moteur et sortie...")
                    break
                
                elif command == 'f' or command == 'forward':
                    motor.forward()
                
                elif command == 'b' or command == 'backward':
                    motor.backward()
                
                elif command == 's' or command == 'stop':
                    motor.stop()
                
                elif command == 'i' or command == 'info':
                    status = motor.get_status()
                    print(f"\n📊 État du moteur:")
                    print(f"   Activé: {status['enabled']}")
                    print(f"   Direction: {status['direction']}")
                    print(f"   Vitesse: 100% (fixe, pas de PWM)")
                
                elif command == 't' or command == 'test':
                    run_automatic_test(motor)
                
                elif command == 'h' or command == 'help':
                    print_menu()
                
                else:
                    print(f"❌ Commande inconnue: {command}")
                    print("   Tapez 'h' pour afficher l'aide")
                
            except EOFError:
                print("\n\n👋 EOF détecté, sortie...")
                break
            except KeyboardInterrupt:
                print("\n\n⚠️  Ctrl+C détecté")
                motor.stop()
                response = input("Voulez-vous quitter? (o/n): ").strip().lower()
                if response in ('o', 'y', 'oui', 'yes'):
                    break
                else:
                    print("Reprise...")
                    continue
    
    finally:
        motor.cleanup()
        print("\n✅ GPIO nettoyés, au revoir!\n")

if __name__ == '__main__':
    main()
