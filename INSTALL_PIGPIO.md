# Installation rapide de pigpio sur Raspberry Pi

## 🚀 Installation automatique (recommandé)

```bash
cd /opt/tubpi
sudo ./install_services_pigpio.sh
# Choisir option 1 (pigpio)
```

Le script va maintenant :
1. ✅ Installer les dépendances de compilation (gcc, make)
2. ✅ Compiler et installer pigpio depuis les sources
3. ✅ Créer le service systemd pour pigpiod
4. ✅ Démarrer le daemon automatiquement

---

## 🔧 Installation manuelle (si le script échoue)

### 1. Installer les dépendances

```bash
sudo apt update
sudo apt install -y python3-dev python3-pip gcc make wget unzip
```

### 2. Compiler pigpio depuis les sources

```bash
cd /tmp
wget https://github.com/joan2937/pigpio/archive/master.zip -O pigpio.zip
unzip pigpio.zip
cd pigpio-master
make
sudo make install
cd /
rm -rf /tmp/pigpio /tmp/pigpio.zip
```

### 3. Installer le module Python

```bash
sudo pip3 install --break-system-packages pigpio
```

### 4. Créer le service systemd

```bash
sudo tee /etc/systemd/system/pigpiod.service << 'EOF'
[Unit]
Description=Pigpio daemon
After=network.target

[Service]
Type=forking
ExecStart=/usr/local/bin/pigpiod -l
ExecStop=/bin/systemctl kill pigpiod
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
```

### 5. Activer et démarrer pigpiod

```bash
sudo systemctl daemon-reload
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
sudo systemctl status pigpiod
```

---

## ✅ Vérification

### Tester le daemon

```bash
# Vérifier que pigpiod tourne
sudo systemctl status pigpiod

# Ou vérifier le processus
pgrep pigpiod
```

### Tester le module Python

```bash
python3 << 'EOF'
import pigpio
pi = pigpio.pi()
if pi.connected:
    print("✓ pigpio connecté au daemon")
    print(f"  Version: {pi.get_hardware_revision()}")
    pi.stop()
else:
    print("✗ Impossible de se connecter au daemon pigpiod")
    print("  Vérifier: sudo systemctl status pigpiod")
EOF
```

### Tester le motor driver

```bash
cd /opt/tubpi
python3 src/motor_driver_pigpio.py

# Ou test automatique
python3 src/motor_driver_pigpio.py test
```

---

## 🐛 Dépannage

### Erreur "Cannot connect to pigpio daemon"

```bash
# Vérifier que le daemon tourne
sudo systemctl status pigpiod

# Si arrêté, démarrer
sudo systemctl start pigpiod

# Voir les logs
sudo journalctl -u pigpiod -n 50
```

### Daemon démarre puis s'arrête

```bash
# Vérifier les permissions GPIO
ls -l /dev/gpiochip* /dev/gpiomem

# Lancer pigpiod en mode debug
sudo killall pigpiod
sudo /usr/local/bin/pigpiod -l

# Si ça fonctionne, le problème vient du service systemd
```

### Module Python "No module named 'pigpio'"

```bash
# Réinstaller le module
sudo pip3 install --break-system-packages --force-reinstall pigpio

# Vérifier l'installation
python3 -c "import pigpio; print(pigpio.__file__)"
```

### Compilation échoue

```bash
# Installer toutes les dépendances
sudo apt install -y build-essential python3-dev python3-pip gcc make

# Réessayer la compilation
cd /tmp
wget https://github.com/joan2937/pigpio/archive/master.zip -O pigpio.zip
unzip pigpio.zip
cd pigpio-master
make
sudo make install
```

---

## 📊 Comparaison avec rpi-lgpio

| Aspect | rpi-lgpio | pigpio |
|--------|-----------|--------|
| Installation | `apt install python3-rpi-lgpio` | Compilation nécessaire |
| Daemon requis | ❌ Non | ✅ Oui (pigpiod) |
| Performance | Standard | Haute |
| PWM | Logiciel | Matériel |
| Callbacks | ~1ms | <100µs |
| Compatibilité | Pi 5 principalement | Tous les Pi |

---

## 🎯 Utilisation après installation

### Avec le script d'installation

```bash
cd /opt/tubpi
sudo ./install_services_pigpio.sh
# Choisir option 1 (pigpio)
# Le script crée automatiquement le lien motor_driver.py → motor_driver_pigpio.py
```

### Manuellement

```bash
cd /opt/tubpi/src

# Créer un lien symbolique
ln -sf motor_driver_pigpio.py motor_driver.py

# Ou modifier directement les imports dans vos scripts
# from motor_driver_pigpio import MotorDriver
```

### Vérifier que tout fonctionne

```bash
# Tester le driver
python3 /opt/tubpi/src/motor_driver_pigpio.py

# Lancer les services
sudo systemctl start tubpi-webapp
sudo systemctl start tubpi-onvif-gateway

# Vérifier les logs
sudo journalctl -u tubpi-webapp -f
```

---

## 📚 Références

- [Documentation officielle pigpio](http://abyz.me.uk/rpi/pigpio/)
- [GitHub pigpio](https://github.com/joan2937/pigpio)
- [docs/pigpio-migration.md](docs/pigpio-migration.md) - Guide complet de migration
- [BRANCH_README.md](BRANCH_README.md) - Vue d'ensemble de la branche pigpio

---

**Date**: 2026-04-27  
**Testé sur**: DietPi, Raspberry Pi 5
