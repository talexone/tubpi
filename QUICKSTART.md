# Guide de démarrage rapide - Services Tubpi

Ce guide vous permet d'installer et de configurer Tubpi pour qu'il démarre automatiquement au boot.

## 🚀 Installation en 3 étapes

### 1. Préparer le projet

```bash
# Copier le projet dans /opt/tubpi
sudo mkdir -p /opt/tubpi
sudo cp -r /chemin/vers/tubpi/* /opt/tubpi/
cd /opt/tubpi
```

### 2. Rendre les scripts exécutables

```bash
sudo chmod +x install_services.sh
sudo chmod +x uninstall_services.sh
sudo chmod +x check_services.sh
```

### 3. Installer les services

```bash
sudo ./install_services.sh
```

Le script vous demandera :
- Quels services installer (tous, seulement certains)
- Si vous voulez les démarrer immédiatement

## 📋 Services disponibles

| Service | Port | Description | Utilisateur |
|---------|------|-------------|-------------|
| **tubpi-network-setup** | - | Configure le réseau (eth0/eth1) | root |
| **tubpi-onvif-gateway** | 80 | Proxy ONVIF + interception focus | root |
| **tubpi-webapp** | 5000 | Interface web de contrôle | pi |

## ✅ Vérifier l'installation

```bash
# Vérifier l'état complet
sudo ./check_services.sh

# Ou manuellement
sudo systemctl status tubpi-onvif-gateway
sudo systemctl status tubpi-webapp
```

## 📊 Voir les logs

```bash
# Logs en temps réel
sudo journalctl -u tubpi-onvif-gateway -f

# Tous les logs Tubpi
sudo journalctl -u 'tubpi-*' -f

# Dernières 50 lignes
sudo journalctl -u tubpi-webapp -n 50
```

## 🔄 Gérer les services

```bash
# Redémarrer
sudo systemctl restart tubpi-onvif-gateway

# Arrêter
sudo systemctl stop tubpi-webapp

# Démarrer
sudo systemctl start tubpi-onvif-gateway

# Désactiver le démarrage automatique
sudo systemctl disable tubpi-network-setup

# Activer le démarrage automatique
sudo systemctl enable tubpi-webapp
```

## 🌐 Accéder aux interfaces

Une fois les services démarrés :

- **ONVIF Gateway** : `http://<ip-raspberry>:80`
- **Web App** : `http://<ip-raspberry>:5000`

Pour connaître l'IP du Raspberry Pi :
```bash
hostname -I
```

## ⚙️ Configuration avancée

### Modifier les paramètres

1. Copier le fichier d'exemple :
   ```bash
   cp config.env.example config.env
   ```

2. Éditer `config.env` avec vos paramètres

3. Modifier les services pour charger ce fichier :
   ```bash
   sudo nano /etc/systemd/system/tubpi-onvif-gateway.service
   ```
   
   Ajouter dans la section `[Service]` :
   ```ini
   EnvironmentFile=/opt/tubpi/config.env
   ```

4. Recharger et redémarrer :
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart tubpi-onvif-gateway
   ```

## 🔧 Dépannage

### Le service ne démarre pas

1. Vérifier les logs :
   ```bash
   sudo journalctl -u tubpi-onvif-gateway -n 100
   ```

2. Vérifier les permissions GPIO :
   ```bash
   groups pi | grep gpio
   # Si absent : sudo usermod -a -G gpio pi
   ```

3. Vérifier les dépendances Python :
   ```bash
   pip3 list | grep -E 'flask|RPi.GPIO|requests'
   # Si manquant : pip3 install -r requirements.txt
   ```

### Port déjà utilisé

Si le port 80 ou 5000 est déjà utilisé :

```bash
# Trouver qui utilise le port 80
sudo lsof -i :80

# Modifier le port dans le service
sudo nano /etc/systemd/system/tubpi-webapp.service
# Changer ExecStart pour ajouter --port 8080

sudo systemctl daemon-reload
sudo systemctl restart tubpi-webapp
```

### Le service redémarre en boucle

Cela indique généralement une erreur au démarrage :

```bash
# Voir les logs avec timestamps
sudo journalctl -u tubpi-onvif-gateway -f --since "5 minutes ago"

# Arrêter le service pour diagnostiquer
sudo systemctl stop tubpi-onvif-gateway

# Tester manuellement
cd /opt/tubpi/src
python3 onvif_gateway.py
```

## 🗑️ Désinstallation

```bash
sudo ./uninstall_services.sh
```

Cela :
- Arrête tous les services
- Les désactive
- Supprime les fichiers de service
- Conserve le code dans `/opt/tubpi`

## 📚 Documentation complète

Pour plus de détails :
- [docs/services.md](docs/services.md) - Documentation complète des services
- [docs/troubleshooting.md](docs/troubleshooting.md) - Dépannage
- [docs/software.md](docs/software.md) - Architecture logicielle
- [docs/hardware.md](docs/hardware.md) - Configuration matérielle

## 💡 Conseils

### Pour le développement

Si vous développez activement, il peut être pratique de ne pas démarrer les services automatiquement :

```bash
# Désactiver le démarrage auto
sudo systemctl disable tubpi-onvif-gateway
sudo systemctl disable tubpi-webapp

# Lancer manuellement quand besoin
cd /opt/tubpi/src
python3 web_app.py
```

### Pour la production

En production, activez tous les services :

```bash
sudo systemctl enable tubpi-network-setup
sudo systemctl enable tubpi-onvif-gateway
sudo systemctl enable tubpi-webapp
```

Et surveillez régulièrement :

```bash
# Créer un alias pratique
echo "alias tubpi-status='sudo systemctl status tubpi-*'" >> ~/.bashrc
source ~/.bashrc

# Utiliser
tubpi-status
```

## 🆘 Support

Si vous rencontrez des problèmes :

1. Exécutez le script de vérification : `sudo ./check_services.sh`
2. Consultez les logs : `sudo journalctl -u tubpi-onvif-gateway -n 100`
3. Vérifiez la documentation dans `docs/`
4. Testez manuellement le code Python

## 🎯 Checklist post-installation

- [ ] Les 3 services sont installés
- [ ] Les services activés démarrent au boot
- [ ] L'utilisateur `pi` est dans le groupe `gpio`
- [ ] Les dépendances Python sont installées
- [ ] Le port 80 est accessible (ONVIF Gateway)
- [ ] Le port 5000 est accessible (Web App)
- [ ] Les GPIO sont fonctionnels (test avec `python3 src/motor_driver.py`)
- [ ] L'encodeur fonctionne (test avec `python3 src/test_encoder.py`)
- [ ] Les capteurs de fin de course fonctionnent

Bon démarrage avec Tubpi ! 🚀
