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
- GPIO 23 : capteur de fin de course avant (forward) - capteur devant, déclenché en premier lors du mouvement vers l'avant
- GPIO 24 : capteur de fin de course arrière (backward) - capteur reculé, déclenché en premier lors du mouvement vers l'arrière
- Pull-up interne activé : HIGH = libre, LOW = déclenché

**Note :** Les deux capteurs sont montés sur le même PCB devant la caméra (côté droit), décalés de 2cm, permettant une détection séquentielle en fin de course.

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

## Gestion de l'encodeur de position

### Configuration
L'encodeur HEDS en quadrature est configuré automatiquement lors de l'initialisation de `MotorDriver` :
- GPIO 17 : Canal A de l'encodeur
- GPIO 27 : Canal B de l'encodeur
- GPIO 22 : Signal Index (non utilisé actuellement)
- Détection par interruptions sur les deux canaux pour un suivi précis en temps réel
- **Optimisation** : bouncetime de 1ms et lock non-bloquant pour éviter les ralentissements système

### Mesures de position et distance

Le système maintient trois compteurs indépendants :

1. **Position actuelle** (`position_pulses`, `position_mm`)
   - Position relative depuis la dernière calibration
   - Peut être négative (si on recule par rapport à la référence)
   - Réinitialisée à zéro lors de la calibration

2. **Distance de session** (`session_distance_mm`, `session_pulses`)
   - Distance totale parcourue depuis le démarrage
   - Toujours positive (cumul des mouvements avant et arrière)
   - Réinitialisable manuellement

3. **Distance totale** (`total_distance_mm`, `total_pulses`)
   - Distance cumulative sur toute la durée de vie du système
   - Toujours positive
   - Conservée même après redémarrage (si persistée)

### Calibration mécanique

La conversion impulsions → millimètres dépend de votre configuration mécanique :

```python
# Formule de calcul
MM_PER_PULSE = (Circonférence_poulie_mm) / (Impulsions_par_tour_encodeur)

# Exemple : poulie Ø30mm avec encodeur 100 impulsions/tour
MM_PER_PULSE = (π × 30) / 100 = 0.9425 mm/impulsion

# Configuration dans le code
driver.set_mm_per_pulse(0.9425)
```

### API disponibles

#### Méthodes publiques
```python
# Obtenir la position actuelle
position_pulses = motor.get_encoder_position()  # en impulsions
position_mm = motor.get_encoder_distance()      # en millimètres

# Obtenir les distances parcourues
total_mm = motor.get_total_distance_traveled()    # distance totale
session_mm = motor.get_session_distance_traveled()  # distance de session

# Obtenir toutes les statistiques
stats = motor.get_encoder_stats()
# Retourne: {
#   'position_pulses': int,
#   'position_mm': float,
#   'total_distance_mm': float,
#   'session_distance_mm': float,
#   'total_pulses': int,
#   'session_pulses': int,
#   'mm_per_pulse': float
# }

# Réinitialiser la position
motor.reset_encoder_position()  # Position → 0

# Réinitialiser le compteur de session
motor.reset_session_distance()

# Configurer la calibration mécanique
motor.set_mm_per_pulse(0.9425)
```

#### Endpoints web
```bash
# Obtenir les statistiques complètes (inclut encodeur)
GET /status
# Retourne: {
#   'available': bool,
#   'limit_switches': {...},
#   'can_move_forward': bool,
#   'can_move_backward': bool,
#   'encoder': {
#     'position_pulses': int,
#     'position_mm': float,
#     'total_distance_mm': float,
#     'session_distance_mm': float,
#     ...
#   }
# }

# Obtenir uniquement les informations de l'encodeur
GET /encoder

# Réinitialiser la position de l'encodeur
POST /encoder/reset
```

### Test de l'encodeur
Pour tester l'encodeur manuellement :
```bash
cd src
python3 test_encoder.py
```

Le script de test permet de :
- Visualiser la position en temps réel
- Tester les mouvements avec suivi de distance
- Réinitialiser la position
- Configurer la calibration mécanique (mm par impulsion)

**Diagnostic de performance** : Si vous constatez des ralentissements (les mouvements prennent plus de temps que prévu), vous pouvez tester sans l'encodeur :
```bash
python3 test_encoder.py --no-encoder
```
Cela désactive temporairement l'encodeur pour vérifier si c'est la source du ralentissement.

**Optimisations implémentées** :
- `bouncetime=1ms` sur les interruptions pour limiter la fréquence
- Lock non-bloquant dans le callback pour éviter de bloquer le thread principal
- Les interruptions manquées (lock occupé) sont ignorées sans perte de fonctionnalité significative

Pour vérifier l'état via l'API web :
```bash
# État complet
curl http://localhost:5000/status

# Statistiques de l'encodeur uniquement
curl http://localhost:5000/encoder

# Réinitialiser la position
curl -X POST http://localhost:5000/encoder/reset
```