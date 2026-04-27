# Fix rapide : webapp service ne peut pas accéder aux GPIO

## Symptôme

```bash
sudo journalctl -u tubpi-webapp -n 20
# Affiche : "Motor driver non disponible"
# ou : "Impossible d'initialiser les GPIO"
# ou : "RuntimeError: Cannot determine SOC peripheral base address"
```

Le service **tubpi-onvif-gateway** (root) fonctionne, mais **tubpi-webapp** (utilisateur non-root) ne peut pas accéder aux GPIO.

## Solution rapide (5 minutes)

### 1. Diagnostic

```bash
cd /opt/tubpi
sudo chmod +x diagnose_gpio.sh
sudo ./diagnose_gpio.sh
```

### 2. Corriger les permissions GPIO

```bash
# Permissions des devices
sudo chown root:gpio /dev/gpiochip* 2>/dev/null
sudo chmod 660 /dev/gpiochip* 2>/dev/null
sudo chown root:gpio /dev/gpiomem 2>/dev/null
sudo chmod 660 /dev/gpiomem 2>/dev/null

# Règle udev permanente
sudo cp /opt/tubpi/systemd/99-gpio.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 3. Mettre à jour le service webapp

```bash
# Copier le service corrigé
sudo cp /opt/tubpi/systemd/tubpi-webapp.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Redémarrer le service
sudo systemctl restart tubpi-webapp
```

### 4. Vérifier

```bash
# Logs du service
sudo journalctl -u tubpi-webapp -n 30

# Devrait afficher : "Motor driver initialisé" ou "Encodeur activé"
```

## Si ça ne marche toujours pas

### Vérifier que l'utilisateur est dans le groupe gpio

```bash
# Remplacer 'dietpi' par votre utilisateur
sudo usermod -a -G gpio dietpi

# Puis redémarrer (nécessaire pour appliquer le groupe)
sudo reboot
```

### Test manuel

```bash
# Se connecter en tant qu'utilisateur du service
sudo -u dietpi bash

# Tester l'accès GPIO
python3 << 'EOF'
import RPi.GPIO as GPIO
try:
    GPIO.setmode(GPIO.BCM)
    print("✓ GPIO accessible")
    GPIO.cleanup()
except Exception as e:
    print(f"✗ Erreur: {e}")
EOF
```

## Explication

### Raspberry Pi 5

Sur Pi 5, les GPIO sont accessibles via `/dev/gpiochip*` au lieu de `/dev/gpiomem`.

**Problème** : systemd applique des restrictions de sécurité qui bloquent l'accès aux devices pour les services non-root.

**Solution** : Ajouter `DeviceAllow` dans le fichier de service pour autoriser explicitement l'accès.

Le fichier `tubpi-webapp.service` inclut maintenant :

```ini
[Service]
User=pi                          # Utilisateur non-root
Group=gpio                       # Groupe principal
SupplementaryGroups=gpio         # Groupes supplémentaires
DeviceAllow=/dev/gpiochip0 rw    # Autoriser gpiochip0
DeviceAllow=/dev/gpiochip1 rw    # Autoriser gpiochip1
DeviceAllow=/dev/gpiochip2 rw    # etc.
DeviceAllow=/dev/gpiochip3 rw
DeviceAllow=/dev/gpiochip4 rw
DeviceAllow=/dev/gpiomem rw      # Pour anciens Pi
DevicePolicy=closed              # Bloquer autres devices
```

### Raspberry Pi < 5

Sur Pi 1-4, l'accès se fait via `/dev/gpiomem` qui nécessite :
- Utilisateur dans le groupe `gpio`
- Permissions 660 (rw-rw----)
- Groupe `gpio` propriétaire

## Fichiers modifiés

- ✅ **systemd/tubpi-webapp.service** - DeviceAllow ajouté
- ✅ **systemd/99-gpio.rules** - Règle udev pour permissions automatiques
- ✅ **install_services.sh** - Installation de la règle udev
- ✅ **diagnose_gpio.sh** - Script de diagnostic
- ✅ **check_services.sh** - Vérification GPIO ajoutée

## Réinstallation complète (alternative)

Si vous préférez tout réinstaller :

```bash
cd /opt/tubpi

# Arrêter les services
sudo systemctl stop tubpi-webapp tubpi-onvif-gateway

# Réinstaller avec le script mis à jour
sudo ./install_services.sh

# Le script configure maintenant automatiquement :
# - Règle udev
# - Permissions devices
# - Services avec DeviceAllow
```

## Commandes utiles

```bash
# Diagnostic complet
sudo /opt/tubpi/diagnose_gpio.sh

# Vérifier tous les services
sudo /opt/tubpi/check_services.sh

# Logs webapp
sudo journalctl -u tubpi-webapp -f

# Logs ONVIF gateway
sudo journalctl -u tubpi-onvif-gateway -f

# Redémarrer les services
sudo systemctl restart tubpi-webapp tubpi-onvif-gateway

# Permissions devices
ls -l /dev/gpiochip* /dev/gpiomem 2>/dev/null
```

## Références

- [docs/raspberry-pi-5-gpio.md](raspberry-pi-5-gpio.md) - Guide complet Pi 5
- [docs/services.md](services.md) - Gestion des services
- [docs/installation-dietpi.md](installation-dietpi.md) - Installation DietPi

---

**Dernière mise à jour** : 2026-04-24  
**Testé sur** : Raspberry Pi 5, DietPi
