# Matériel requis

## Raspberry Pi
- Raspberry Pi 5 recommandé
- Alternative : Raspberry Pi 3B si besoin, mais privilégier le Pi 5 pour les performances et la compatibilité.

## Motorisation
- Carte `RPI Motor Driver Board`
- Moteur DC ou moteur pas à pas compatible avec le rail
- Alimentation moteur 12V ou 24V selon le moteur
- RPi Motor Driver Board

Raspberry Pi Expansion Board, DC Motor / Stepper Motor Driver
### Introduction

Interface definitions
Interface	wiringPi	BCM
M1	        P28	        20
M2	        P29	        21
PWMA	    P25	        26
M3	        P22 	    6
M4	        P23	        13
PWMB	    P26	        12

M1 and M2 are connected to the right motor, while M3 and M4 are connected to the left motor. PWMA and PWMB are output enable pins, active high enable. When they are driven to high level, the PWM pulse will be outputted from M1, M2, M3 and M4, so as to control the speed of the robot.

Control work
M1	M2	M3	M4	Descriptions
1	0	1	0	When the motors rotate forwards, the robot goes straight
0	1	0	1	When the motors rotate backwards, the robot draws back
0	0	1	0	When the right motor stops and left motor rotates forwards, the robot turns right
1	0	0	0	When the left motor stops and right motor rotates forwards, the robot turns left
0	0	0	0	When the motors stop, the robot stops


## Capteurs
- Capteurs de fin de course pour chaque extrémité du rail
### Schéma de connexion
Comme vous avez deux capteurs, vous allez devoir doubler le câblage sur votre Mini Base

Composant           Patte Capteur       Connexion Raspberry Pi
LED 1 (Haut)        A (Anode)           3.3V (via résistance 220 Ohm)
                    K (Cathode)         GND
LED 1 (Bas)         A (Anode)           3.3V (via résistance 220 Ohm)
                    K (Cathode)         GND
Phototransistor 1   C (Collecteur)     GPIO 23 (capteur arrière/backward)
                    E (Émetteur)        GND
Phototransistor 2   C (Collecteur)     GPIO 24 (capteur avant/forward)
                    E (Émetteur)        GND

### Fonctionnement
- **État normal (faisceau libre)** : Le phototransistor reçoit la lumière, le signal GPIO est HIGH (pull-up activé)
- **Fin de course déclenchée (faisceau coupé)** : Le phototransistor ne reçoit plus de lumière, le signal GPIO passe à LOW
- **Sécurité** : Le moteur s'arrête automatiquement lorsqu'un capteur détecte une fin de course
- **Calibration** : Utilise le capteur arrière comme position de référence (home position)

- Capteurs de position ou encodeur pour mesurer le déplacement
L'encodeur HEDS fonctionne en 5V. S'il envoie ses signaux (A, B, Index) directement dans les pins du Pi, le processeur du CM5 sera endommagé de façon irréversible. Le Level Shifter joue le rôle de traducteur sécurisé.
### Schéma de branchement
Le Level Shifter possède deux côtés : un côté HV (High Voltage - 5V) et un côté LV (Low Voltage - 3.3V).
Côté Encodeur (5V)      Côté Level Shifter      Côté Raspberry Pi (3.3V)
VCC (Pin 4)             HV (Alimentation 5V)    —
GND (Pin 1)             GND (Masse commune)     GND
—                       LV (Référence 3.3V)     Pin 3.3V
Canal A (Pin 3)         HV1 (Entrée 5V)         LV1 $ -> GPIO 17
Canal B (Pin 5)         HV2 (Entrée 5V)         LV2 $ -> GPIO 27
Index I (Pin 2)         HV3 (Entrée 5V)         LV3 $ -> GPIO 22

## Caméra
- Caméra IP PTZ ONVIF (par exemple Dahua)
- Connexion réseau fiable pour le flux vidéo et les commandes

## Mécanique
- Rail solide adapté au poids de la caméra
- Supports de fixation
- Système de transmission : courroie, pignon ou engrenage
- Châssis rigide pour limiter les vibrations
