# Tubpi - Caméra sur rail pilotée par Raspberry Pi 5

## Objectif
Développer un système permettant de déplacer automatiquement une caméra sur un rail à l'aide d'un Raspberry Pi 5 et d'une caméra PTZ ONVIF.

## Besoin
- Déplacer la caméra le long d'un rail avec commande avant/arrière.
- Prendre en charge les commandes ONVIF PTZ focus+ / focus- pour piloter le déplacement.
- Offrir une interface de commande locale ou web.
- Assurer la sécurité avec des capteurs de fin de course et l'arrêt d'urgence.

## Matériel principal
- Raspberry Pi 5
- Carte `RPI Motor Driver Board`
- Moteur DC ou moteur pas à pas adapté au rail
- Capteurs de fin de course ou capteurs de position
- Caméra IP PTZ ONVIF (Dahua ou équivalent)
- Alimentation stable pour le Pi et le moteur
- Châssis / rail, supports, courroie ou engrenages

## Structure du projet
- `plan.md` : plan de développement et besoins
- `README.md` : présentation globale du projet
- `requirements.txt` : dépendances Python
- `src/` : code source du projet
- `docs/` : documentation matériel et architecture

## Démarrage
1. Installer l'OS sur le Raspberry Pi 5.
2. Installer les outils système nécessaires (Debian/DietPi) :
   - `apt update`
   - `apt install python3-venv python3-dev build-essential`
3. Créer un environnement virtuel Python et l'activer :
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
4. Installer les dépendances Python via `pip install -r requirements.txt`.
   - Si `RPi.GPIO` échoue, essayez d'installer le paquet système : `apt install python3-rpi.gpio`
5. Vérifier les connexions du moteur et des capteurs.
6. Tester l'accès GPIO avant de lancer le serveur :
   - `python src/motor_driver.py`
   - Pour un test moteur automatique (gauche 10s, droit 10s, arrêt) :
     `python src/motor_driver.py test`
   - Pour tester les capteurs de fin de course :
     `python src/test_limit_switches.py`
7. Lancer le serveur web avec `python src/web_app.py`.
8. Ouvrir un navigateur sur `http://<adresse-du-raspberry-pi>:5000/` pour accéder à la page de test.

## Capteurs de fin de course

Le système intègre des capteurs optoélectroniques (phototransistors) pour détecter les fins de course :

### Configuration matérielle
- **GPIO 23** : capteur de fin de course arrière (backward) - position de référence
- **GPIO 24** : capteur de fin de course avant (forward)
- Type : phototransistors avec LED infrarouge
- Logique : HIGH = libre, LOW = déclenché (faisceau coupé)

### Fonctionnalités de sécurité
- **Arrêt automatique** : le moteur s'arrête dès qu'un capteur est déclenché
- **Prévention** : impossible de démarrer un mouvement si le capteur correspondant est déjà déclenché
- **Calibration** : fonction automatique utilisant le capteur arrière comme position de référence

### Tests et surveillance
```bash
# Test interactif des capteurs
python src/test_limit_switches.py

# État via l'API web
curl http://localhost:5000/status
```

Pour plus de détails, consultez [docs/hardware.md](docs/hardware.md) et [docs/software.md](docs/software.md).

## Passerelle ONVIF
- Exécuter sur le Raspberry Pi : `sudo python src/onvif_gateway.py`
- Le proxy écoute sur le port 80 et relaie les requêtes vers la caméra `192.168.1.108`.
- Les commandes ONVIF `focus+` et `focus-` sont interceptées et pilotent le moteur du rail.
- Les autres requêtes ONVIF sont envoyées normalement à la caméra.

## Améliorations futures
- Programmation de trajectoires automatiques.
- Suivi d'objet et mode automatique.
- Application mobile ou API RESTful avancée.
