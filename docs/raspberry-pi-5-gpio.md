# Raspberry Pi 5 - Guide de compatibilité GPIO

## Problème

Le Raspberry Pi 5 utilise un nouveau chip RP1 pour les GPIO, ce qui rend l'ancienne bibliothèque `RPi.GPIO` **incompatible**.

### Erreur typique :
```
RuntimeError: Cannot determine SOC peripheral base address
```

## Solution : rpi-lgpio

La bibliothèque **`rpi-lgpio`** est un remplacement compatible avec l'API `RPi.GPIO` qui fonctionne sur Raspberry Pi 5.

### Installation immédiate (DietPi/Debian)

```bash
# 1. Désinstaller l'ancienne bibliothèque (si installée)
sudo apt remove python3-rpi.gpio
pip3 uninstall RPi.GPIO

# 2. Installer rpi-lgpio
sudo apt install python3-rpi-lgpio

# OU via pip
pip3 install --break-system-packages rpi-lgpio

# 3. Vérifier l'installation
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); print('GPIO OK')"
```

### Installation complète via le script

Le script d'installation a été mis à jour pour installer automatiquement `rpi-lgpio` :

```bash
cd /opt/tubpi
sudo ./install_services.sh
```

## Compatibilité du code

**Bonne nouvelle** : `rpi-lgpio` fournit l'API `RPi.GPIO`, donc **aucune modification du code** n'est nécessaire !

```python
# Le code existant fonctionne directement
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(20, GPIO.OUT)
GPIO.output(20, GPIO.HIGH)
# etc.
```

## Vérification après installation

### Test GPIO basique

```bash
python3 << 'EOF'
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(20, GPIO.OUT)
GPIO.output(20, GPIO.HIGH)
GPIO.output(20, GPIO.LOW)
print("✓ GPIO test OK")
GPIO.cleanup()
EOF
```

### Test du moteur

```bash
cd /opt/tubpi/src
python3 motor_driver.py
```

Si ça affiche "Initialiser les GPIO" et "Encodeur activé", c'est bon !

### Test des services

```bash
# Redémarrer les services
sudo systemctl restart tubpi-onvif-gateway
sudo systemctl restart tubpi-webapp

# Vérifier les logs
sudo journalctl -u tubpi-onvif-gateway -n 20
```

Vous devriez voir "Motor driver initialisé" au lieu de "Motor driver non disponible".

## Dépannage

### Toujours l'erreur "Cannot determine SOC peripheral base address"

1. **Vérifier quelle bibliothèque est installée** :
   ```bash
   python3 << 'EOF'
   import sys
   try:
       import RPi.GPIO
       print(f"RPi.GPIO trouvé : {RPi.GPIO.__file__}")
   except ImportError:
       print("RPi.GPIO non trouvé")
   
   try:
       import lgpio
       print(f"lgpio trouvé : {lgpio.__file__}")
   except ImportError:
       print("lgpio non trouvé")
   EOF
   ```

2. **Si RPi.GPIO pointe vers l'ancienne version** :
   ```bash
   # Lister les paquets installés
   dpkg -l | grep -i gpio
   pip3 list | grep -i gpio
   
   # Désinstaller l'ancienne version
   sudo apt remove python3-rpi.gpio
   pip3 uninstall RPi.GPIO
   
   # Réinstaller rpi-lgpio
   sudo apt install python3-rpi-lgpio
   ```

3. **Vérifier les permissions** :
   ```bash
   # Vérifier /dev/gpiochip*
   ls -l /dev/gpiochip*
   
   # Devrait montrer : crw-rw---- 1 root gpio
   
   # Vérifier que l'utilisateur est dans le groupe gpio
   groups
   # ou
   groups dietpi
   
   # Si absent, ajouter :
   sudo usermod -a -G gpio dietpi
   # puis déconnexion/reconnexion ou reboot
   ```

### Erreur "Permission denied" sur /dev/gpiochip

```bash
# Vérifier les permissions
ls -l /dev/gpiochip*

# Devrait montrer: crw-rw---- 1 root gpio
# Si le groupe n'est pas gpio:
sudo chown root:gpio /dev/gpiochip*
sudo chmod 660 /dev/gpiochip*

# Ajouter l'utilisateur au groupe gpio
sudo usermod -a -G gpio $USER

# Installer la règle udev pour rendre permanent
sudo cp systemd/99-gpio.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# Recharger les groupes (déconnexion/reconnexion ou reboot)
sudo reboot
```

### Service webapp ne peut pas accéder aux GPIO

Si le service `tubpi-webapp` affiche "Motor driver non disponible" :

**Symptôme**: Le service ONVIF gateway (root) fonctionne mais webapp (utilisateur non-root) ne peut pas accéder aux GPIO.

**Cause**: Restrictions systemd qui bloquent l'accès aux devices GPIO.

**Solution**:

```bash
# 1. Diagnostic complet
sudo /opt/tubpi/diagnose_gpio.sh

# 2. Corriger les permissions
sudo chown root:gpio /dev/gpiochip*
sudo chmod 660 /dev/gpiochip*

# 3. Installer la règle udev
sudo cp /opt/tubpi/systemd/99-gpio.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# 4. Mettre à jour le service avec DeviceAllow
sudo cp /opt/tubpi/systemd/tubpi-webapp.service /etc/systemd/system/
sudo systemctl daemon-reload

# 5. Redémarrer le service
sudo systemctl restart tubpi-webapp

# 6. Vérifier les logs
sudo journalctl -u tubpi-webapp -n 30
```

Le service webapp nécessite maintenant :
- User dans le groupe **gpio**
- **DeviceAllow** pour `/dev/gpiochip*` et `/dev/gpiomem`
- **DevicePolicy=closed** pour sécurité
- Pas de **PrivateTmp** qui bloquerait l'accès

Le fichier de service inclut :
```ini
[Service]
User=pi
Group=gpio
SupplementaryGroups=gpio
DeviceAllow=/dev/gpiochip0 rw
DeviceAllow=/dev/gpiochip1 rw
DeviceAllow=/dev/gpiochip2 rw
DeviceAllow=/dev/gpiochip3 rw
DeviceAllow=/dev/gpiochip4 rw
DeviceAllow=/dev/gpiomem rw
DevicePolicy=closed
```

### Le service démarre mais le moteur n'est pas disponible

```bash
# Vérifier les logs détaillés
sudo journalctl -u tubpi-onvif-gateway -n 100 | grep -A5 -B5 "GPIO"

# Tester manuellement
cd /opt/tubpi/src
sudo python3 onvif_gateway.py
# Vérifier si "Motor driver initialisé" apparaît
```

## Différences entre RPi.GPIO et rpi-lgpio

Pour l'utilisateur, **aucune différence** ! L'API est identique.

En interne :
- **RPi.GPIO** : accès direct au matériel via `/dev/mem` (ancien modèle)
- **rpi-lgpio** : utilise `lgpio` qui communique avec le kernel via `/dev/gpiochip*` (nouveau modèle)

## Compatibilité multi-plateformes

Le code Tubpi fonctionne maintenant sur :
- ✅ Raspberry Pi 3 (avec RPi.GPIO ou rpi-lgpio)
- ✅ Raspberry Pi 4 (avec RPi.GPIO ou rpi-lgpio)
- ✅ Raspberry Pi 5 (avec rpi-lgpio uniquement)

## Mise à jour depuis une installation existante

Si vous aviez déjà installé Tubpi avec l'ancienne bibliothèque :

```bash
# 1. Arrêter les services
sudo systemctl stop tubpi-onvif-gateway
sudo systemctl stop tubpi-webapp

# 2. Désinstaller RPi.GPIO
sudo apt remove python3-rpi.gpio
pip3 uninstall RPi.GPIO

# 3. Installer rpi-lgpio
sudo apt install python3-rpi-lgpio

# 4. Redémarrer les services
sudo systemctl start tubpi-onvif-gateway
sudo systemctl start tubpi-webapp

# 5. Vérifier
sudo journalctl -u tubpi-onvif-gateway -n 20
```

## Références

- [rpi-lgpio GitHub](https://github.com/joan2937/lg)
- [Raspberry Pi 5 GPIO Documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header)
- [lgpio Documentation](https://abyz.me.uk/lg/index.html)

## Résumé commandes rapides

```bash
# Installation complète sur Raspberry Pi 5
sudo apt update
sudo apt install python3-rpi-lgpio python3-flask python3-requests
cd /opt/tubpi
sudo ./install_services.sh

# Vérification
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); print('GPIO OK')"
sudo systemctl status tubpi-onvif-gateway
```
