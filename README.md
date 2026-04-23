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
   - Pour tester l'encodeur de position :
     `python src/test_encoder.py`
7. Lancer le serveur web avec `python src/web_app.py`.
8. Ouvrir un navigateur sur `http://<adresse-du-raspberry-pi>:5000/` pour accéder à la page de test.

## Capteurs de fin de course

Le système intègre des capteurs optoélectroniques (phototransistors) pour détecter les fins de course :

### Configuration matérielle
- **GPIO 23** : capteur de fin de course avant (forward) - capteur devant
- **GPIO 24** : capteur de fin de course arrière (backward) - capteur reculé, position de référence
- Type : phototransistors avec LED infrarouge
- Logique : HIGH = libre, LOW = déclenché (faisceau coupé)
- **Montage physique** : les deux capteurs sont fixés devant la caméra sur le côté droit, décalés de 2cm sur le même PCB (montés en opposition). Lors d'une fin de course, le premier capteur se déclenche puis le deuxième.

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

## Encodeur de position

Le système intègre un encodeur HEDS en quadrature pour mesurer précisément la position et les distances parcourues :

### Configuration matérielle
- **GPIO 17** : Canal A de l'encodeur (via Level Shifter 5V → 3.3V)
- **GPIO 27** : Canal B de l'encodeur (via Level Shifter 5V → 3.3V)
- **GPIO 22** : Signal Index (via Level Shifter 5V → 3.3V)
- Type : Encodeur HEDS en quadrature
- **Protection obligatoire** : Level Shifter pour convertir les signaux 5V de l'encodeur en 3.3V pour le Raspberry Pi

### Mesures disponibles
Le système suit trois types de données :
1. **Position actuelle** : position relative depuis la dernière calibration (en mm, peut être négative)
2. **Distance de session** : distance totale parcourue depuis le démarrage (en mm, toujours positive)
3. **Distance totale** : distance cumulative sur toute la durée de vie (en mm, toujours positive)

### Calibration mécanique
La conversion impulsions → millimètres dépend de votre configuration :
```
MM_PER_PULSE = (Circonférence_poulie_mm) / (Impulsions_par_tour_encodeur)
```
Exemple : poulie Ø30mm avec encodeur 100 imp/tour → `MM_PER_PULSE = 0.9425 mm`

### Tests et API
```bash
# Test interactif de l'encodeur
python src/test_encoder.py

# Test sans encodeur (diagnostic de performance)
python src/test_encoder.py --no-encoder

# Statistiques via l'API web
curl http://localhost:5000/encoder

# État complet (capteurs + encodeur)
curl http://localhost:5000/status

# Réinitialiser la position
curl -X POST http://localhost:5000/encoder/reset
```

**Note sur les performances** : L'encodeur utilise des interruptions optimisées (bouncetime=1ms, lock non-bloquant) pour éviter les ralentissements système. Si vous constatez des problèmes de timing, utilisez le mode `--no-encoder` pour diagnostiquer.

Pour plus de détails sur la calibration et l'API, consultez [docs/software.md](docs/software.md).

## Passerelle ONVIF
- Exécuter sur le Raspberry Pi : `sudo python src/onvif_gateway.py`
- Le proxy écoute sur le port 80 et relaie les requêtes vers la caméra `192.168.1.108`.
- Les commandes ONVIF `focus+` et `focus-` sont interceptées et pilotent le moteur du rail.
- Les autres requêtes ONVIF sont envoyées normalement à la caméra.

## Améliorations futures
- Programmation de trajectoires automatiques.
- Suivi d'objet et mode automatique.
- Application mobile ou API RESTful avancée.
