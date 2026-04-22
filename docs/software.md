# Architecture logicielle

## Objectifs logiciels
- Piloter le moteur du rail depuis le Raspberry Pi
- Intercepter les commandes ONVIF focus+ / focus- pour les mapper au mouvement du rail
- Proposer une interface de contrôle local ou web
- Assurer des arrêts d'urgence et la gestion des limites

## Modules principaux
- `src/motor_driver.py` : gestion du pilote moteur et des commandes de déplacement
- `src/camera_onvif.py` : gestion de la caméra ONVIF et des commandes PTZ
- `src/web_app.py` : interface web simple pour commander le rail

## Flux de données
1. Le client envoie une commande via l’interface web ou déclenche un événement ONVIF.
2. Le module ONVIF traduit la commande focus+ / focus- en instruction de mouvement.
3. Le moteur est actionné dans la bonne direction et à la bonne vitesse.
4. Les capteurs de fin de course ou de position valident les limites de déplacement.
5. Le serveur renvoie l’état et les erreurs éventuelles.
## Gestion des capteurs de fin de course

### Configuration
Les capteurs de fin de course sont configurés automatiquement lors de l'initialisation de `MotorDriver` :
- GPIO 23 : capteur de fin de course arrière (backward)
- GPIO 24 : capteur de fin de course avant (forward)
- Pull-up interne activé : HIGH = libre, LOW = déclenché

### Fonctionnement
Le système vérifie l'état des capteurs :
- **Avant le démarrage** : empêche le mouvement si le capteur est déjà déclenché
- **Pendant le mouvement** : arrête automatiquement le moteur si un capteur est déclenché
- **Calibration** : utilise le capteur arrière comme position de référence (home position)

### API disponibles

#### Méthodes publiques
```python
# Obtenir l'état des capteurs
status = motor.get_limit_switches_status()
# Retourne: {'forward': bool, 'backward': bool, 'available': bool}

# Vérifier si un mouvement est possible
can_forward = motor.can_move_forward()
can_backward = motor.can_move_backward()

# Calibration automatique
result = motor.calibrate()
# Retourne: {'success': bool, 'message': str}
```

#### Endpoints web
```bash
# Obtenir l'état du système
GET /status
# Retourne: {
#   'available': bool,
#   'limit_switches': {'forward': bool, 'backward': bool},
#   'can_move_forward': bool,
#   'can_move_backward': bool
# }
```

### Test des capteurs
Pour tester les capteurs manuellement :
```bash
cd src
python3 src/test_limit_switches.py
```

Pour vérifier l'état via l'API web :
```bash
curl http://localhost:5000/status
```