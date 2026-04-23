# Installation sur DietPi et autres distributions

Ce guide couvre l'installation de Tubpi sur différentes distributions Raspberry Pi OS, avec un focus sur DietPi.

## Différences entre distributions

### Raspberry Pi OS (anciennement Raspbian)
- **Utilisateur par défaut** : `pi`
- **Python** : versions anciennes permettent `pip install` système
- **GPIO** : groupe `gpio` préconfiguré

### DietPi
- **Utilisateur par défaut** : `root` ou `dietpi`
- **Python** : Python 3.13+ avec protection `externally-managed-environment`
- **GPIO** : nécessite configuration manuelle du groupe

### Debian/Ubuntu
- **Utilisateur par défaut** : variable (souvent `debian` ou utilisateur créé)
- **Python** : protection `externally-managed-environment` activée
- **GPIO** : configuration manuelle requise

## Installation automatique

Le script `install_services.sh` détecte automatiquement :
- L'utilisateur non-root (via `$SUDO_USER` ou recherche automatique)
- Le système de gestion des paquets Python
- Les permissions GPIO

### Étapes d'installation

```bash
# 1. Copier le projet
sudo mkdir -p /opt/tubpi
sudo cp -r /chemin/vers/tubpi/* /opt/tubpi/
cd /opt/tubpi

# 2. Rendre les scripts exécutables
sudo chmod +x install_services.sh
sudo chmod +x uninstall_services.sh
sudo chmod +x check_services.sh

# 3. Installer
sudo ./install_services.sh
```

## Gestion des dépendances Python

### DietPi et Debian récents (Python 3.13+)

Le script installe les dépendances dans cet ordre :

1. **Paquets système APT** (recommandé) :
   ```bash
   sudo apt update
   sudo apt install python3-flask python3-requests python3-rpi.gpio
   ```

2. **Pip avec `--break-system-packages`** (si paquets manquants) :
   ```bash
   pip3 install --break-system-packages -r requirements.txt
   ```

### Alternative : environnement virtuel

Si vous préférez utiliser un environnement virtuel (non recommandé pour les services systemd) :

```bash
# Créer l'environnement virtuel
python3 -m venv /opt/tubpi/.venv

# Activer
source /opt/tubpi/.venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Modifier les services pour utiliser le venv
# Éditer ExecStart dans les fichiers .service :
# ExecStart=/opt/tubpi/.venv/bin/python3 /opt/tubpi/src/onvif_gateway.py
```

## Configuration utilisateur

### Détection automatique

Le script détecte l'utilisateur dans cet ordre :
1. `$SUDO_USER` (utilisateur qui a lancé sudo)
2. `pi` (si existe)
3. `dietpi` (si existe)
4. `debian` (si existe)
5. `ubuntu` (si existe)

### Configuration manuelle

Si vous voulez forcer un utilisateur spécifique :

```bash
# Avant d'exécuter install_services.sh, définir :
export TARGET_USER="votre_utilisateur"
sudo -E ./install_services.sh
```

Ou modifier manuellement le service webapp :

```bash
sudo nano /etc/systemd/system/tubpi-webapp.service
```

Changer la ligne `User=pi` en `User=votre_utilisateur`.

## Permissions GPIO

### Vérification

```bash
# Vérifier si l'utilisateur est dans le groupe gpio
groups dietpi
# ou
groups $USER
```

### Ajout manuel

```bash
# Ajouter au groupe gpio
sudo usermod -a -G gpio dietpi

# Vérifier
groups dietpi

# Note : déconnexion/reconnexion nécessaire pour appliquer
```

### Test GPIO

```bash
# Tester l'accès GPIO
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); print('GPIO OK')"
```

## Spécificités DietPi

### Configuration réseau

DietPi utilise son propre système de configuration réseau (`dietpi-config`).

Si vous activez `tubpi-network-setup.service`, assurez-vous que :
- Il ne conflit pas avec la configuration DietPi
- Les interfaces `eth0` et `eth1` sont correctement identifiées

**Vérification** :

```bash
ip addr show
# Vérifier que eth0 et eth1 existent
```

**Alternative** : Configurer le réseau manuellement via `dietpi-config` et ne pas activer `tubpi-network-setup`.

### Services système

DietPi démarre avec un système minimal. Vérifier les services nécessaires :

```bash
# Vérifier que systemd-networkd ou networking est actif
systemctl status systemd-networkd
# ou
systemctl status networking
```

### Optimisation mémoire

DietPi est optimisé pour utiliser peu de mémoire. Si vous avez des problèmes :

```bash
# Vérifier la mémoire disponible
free -h

# Augmenter le swap si nécessaire
sudo /boot/dietpi/func/dietpi-set_swapfile 1024
```

## Vérification post-installation

```bash
# Script de vérification complet
sudo ./check_services.sh

# Vérifications manuelles
sudo systemctl status tubpi-onvif-gateway
sudo systemctl status tubpi-webapp
sudo journalctl -u tubpi-onvif-gateway -n 50
```

## Dépannage DietPi

### Python externally-managed

**Erreur** :
```
error: externally-managed-environment
```

**Solution automatique** : Le script utilise maintenant `apt install python3-*` en priorité.

**Solution manuelle** :
```bash
sudo apt install python3-flask python3-requests python3-rpi.gpio
```

### Utilisateur 'pi' inexistant

**Erreur** :
```
groups: 'pi': no such user
usermod: user 'pi' does not exist
```

**Solution automatique** : Le script détecte maintenant l'utilisateur actuel.

**Solution manuelle** :
```bash
# Créer un utilisateur pi si nécessaire
sudo useradd -m -G gpio,sudo pi
sudo passwd pi
```

### Port 80 déjà utilisé

DietPi peut avoir d'autres services sur le port 80 (lighttpd, nginx).

**Vérification** :
```bash
sudo lsof -i :80
sudo systemctl list-units --type=service --state=running | grep -E 'nginx|lighttpd|apache'
```

**Solution** :
```bash
# Arrêter le service conflictuel
sudo systemctl stop lighttpd
sudo systemctl disable lighttpd

# Ou modifier le port de tubpi-onvif-gateway
sudo nano /etc/systemd/system/tubpi-onvif-gateway.service
# Modifier pour utiliser le port 8080 par exemple
```

### GPIO non accessible

**Erreur** :
```
RuntimeError: No access to /dev/mem
```

**Solution** :
```bash
# Vérifier les permissions /dev/gpiomem
ls -l /dev/gpiomem

# Devrait être : crw-rw---- 1 root gpio

# Vérifier le groupe de l'utilisateur
groups dietpi

# Recharger les groupes (déconnexion/reconnexion)
# ou redémarrer
sudo reboot
```

## Tests après installation

### Test minimal

```bash
# Test GPIO
python3 << EOF
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(20, GPIO.OUT)
GPIO.output(20, GPIO.HIGH)
print("GPIO test OK")
GPIO.cleanup()
EOF
```

### Test moteur

```bash
cd /opt/tubpi/src
python3 motor_driver.py
```

### Test web app

```bash
# Démarrer manuellement
cd /opt/tubpi/src
python3 web_app.py
# Puis ouvrir http://<ip-raspberry>:5000
```

### Test ONVIF gateway

```bash
# Démarrer manuellement
cd /opt/tubpi/src
sudo python3 onvif_gateway.py
# Puis tester avec curl
curl http://localhost
```

## Configuration réseau avancée

### DietPi avec deux interfaces

Si vous utilisez deux interfaces Ethernet :

```bash
# Identifier les interfaces
ip addr show

# Configurer via dietpi-config
sudo dietpi-config
# 6 - Network Options
# 1 - Network Adapters

# Ou manuellement via /etc/network/interfaces
sudo nano /etc/network/interfaces
```

Exemple de configuration :
```
auto eth0
iface eth0 inet static
    address 192.168.11.28
    netmask 255.255.255.0
    gateway 192.168.11.1

auto eth1
iface eth1 inet static
    address 192.168.1.30
    netmask 255.255.255.0
```

## Logs et surveillance

### Journalctl sur DietPi

```bash
# Logs depuis le boot
sudo journalctl -b

# Logs d'un service
sudo journalctl -u tubpi-onvif-gateway

# Logs en temps réel
sudo journalctl -f

# Logs avec priorité
sudo journalctl -p err
```

### Surveillance ressources

```bash
# htop (installer si nécessaire)
sudo apt install htop
htop

# Utilisation CPU/Mémoire par service
systemctl status tubpi-onvif-gateway

# Statistiques détaillées
systemd-cgtop
```

## Résumé des commandes DietPi

```bash
# Installation complète
sudo apt update
sudo apt install python3-flask python3-requests python3-rpi.gpio
sudo mkdir -p /opt/tubpi
sudo cp -r /chemin/vers/tubpi/* /opt/tubpi/
cd /opt/tubpi
sudo chmod +x install_services.sh check_services.sh uninstall_services.sh
sudo ./install_services.sh

# Vérification
sudo ./check_services.sh

# Test manuel
cd /opt/tubpi/src
python3 motor_driver.py

# Logs
sudo journalctl -u tubpi-onvif-gateway -f
```

## Ressources

- [DietPi Documentation](https://dietpi.com/docs/)
- [Raspberry Pi GPIO](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header)
- [Python RPi.GPIO](https://pypi.org/project/RPi.GPIO/)
- [systemd Documentation](https://www.freedesktop.org/software/systemd/man/)
