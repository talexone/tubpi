# Services systemd Tubpi

Ce document décrit les services systemd disponibles pour automatiser le démarrage de Tubpi.

## Services disponibles

### 1. tubpi-network-setup.service
Configure le réseau du Raspberry Pi pour agir comme passerelle vers la caméra.

**Fonctions :**
- Configure eth0 (réseau local)
- Configure eth1 (vers la caméra)
- Active l'IP forwarding
- Configure les règles NAT

**Type :** oneshot (s'exécute une fois au démarrage)

### 2. tubpi-onvif-gateway.service
Proxy HTTP/ONVIF qui intercepte les commandes focus+/focus- et les traduit en mouvements du rail.

**Fonctions :**
- Écoute sur le port 80 (nécessite root)
- Relaie les requêtes ONVIF vers la caméra
- Intercepte focus+ → move_forward
- Intercepte focus- → move_backward
- Contrôle le moteur via GPIO

**Type :** daemon permanent

### 3. tubpi-webapp.service
Interface web de contrôle du rail de caméra.

**Fonctions :**
- Interface web sur le port 5000
- Boutons de contrôle manuel
- Affichage en temps réel de l'encodeur
- État des capteurs de fin de course

**Type :** daemon permanent

## Installation

### Installation automatique

```bash
# Cloner ou copier le projet dans /opt/tubpi
sudo mkdir -p /opt/tubpi
sudo cp -r /chemin/vers/tubpi/* /opt/tubpi/

# Rendre le script exécutable
sudo chmod +x /opt/tubpi/install_services.sh

# Lancer l'installation
sudo /opt/tubpi/install_services.sh
```

Le script d'installation vous demandera :
1. Quels services activer
2. Si vous voulez les démarrer immédiatement

### Installation manuelle

```bash
# Copier les fichiers de service
sudo cp systemd/*.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer les services (démarrage automatique)
sudo systemctl enable tubpi-network-setup.service
sudo systemctl enable tubpi-onvif-gateway.service
sudo systemctl enable tubpi-webapp.service

# Démarrer les services
sudo systemctl start tubpi-network-setup.service
sudo systemctl start tubpi-onvif-gateway.service
sudo systemctl start tubpi-webapp.service
```

## Gestion des services

### Voir l'état

```bash
# État d'un service
sudo systemctl status tubpi-onvif-gateway

# État de tous les services Tubpi
sudo systemctl status 'tubpi-*'
```

### Démarrer/Arrêter

```bash
# Démarrer
sudo systemctl start tubpi-webapp

# Arrêter
sudo systemctl stop tubpi-onvif-gateway

# Redémarrer
sudo systemctl restart tubpi-onvif-gateway
```

### Activer/Désactiver le démarrage automatique

```bash
# Activer (démarrera au boot)
sudo systemctl enable tubpi-webapp

# Désactiver (ne démarrera pas au boot)
sudo systemctl disable tubpi-network-setup

# Vérifier si activé
sudo systemctl is-enabled tubpi-onvif-gateway
```

### Voir les logs

```bash
# Logs en temps réel
sudo journalctl -u tubpi-onvif-gateway -f

# Dernières 100 lignes
sudo journalctl -u tubpi-webapp -n 100

# Logs depuis le dernier boot
sudo journalctl -u tubpi-onvif-gateway -b

# Logs avec filtres de temps
sudo journalctl -u tubpi-webapp --since "1 hour ago"
sudo journalctl -u tubpi-onvif-gateway --since "2024-04-23 10:00" --until "2024-04-23 11:00"
```

## Désinstallation

### Automatique

```bash
sudo /opt/tubpi/uninstall_services.sh
```

### Manuelle

```bash
# Arrêter les services
sudo systemctl stop tubpi-network-setup
sudo systemctl stop tubpi-onvif-gateway
sudo systemctl stop tubpi-webapp

# Désactiver
sudo systemctl disable tubpi-network-setup
sudo systemctl disable tubpi-onvif-gateway
sudo systemctl disable tubpi-webapp

# Supprimer les fichiers
sudo rm /etc/systemd/system/tubpi-*.service

# Recharger systemd
sudo systemctl daemon-reload
```

## Dépannage

### Le service ne démarre pas

1. Vérifier les logs :
   ```bash
   sudo journalctl -u tubpi-onvif-gateway -n 50
   ```

2. Vérifier les permissions :
   ```bash
   # Pour le moteur, vérifier les permissions GPIO
   groups pi | grep gpio
   
   # Si absent, ajouter :
   sudo usermod -a -G gpio pi
   ```

3. Vérifier les dépendances Python :
   ```bash
   pip3 list | grep -E 'flask|RPi.GPIO|requests'
   ```

### Le service redémarre constamment

Vérifier les logs pour identifier l'erreur :
```bash
sudo journalctl -u tubpi-webapp -f
```

Causes communes :
- Port déjà utilisé (80 ou 5000)
- Erreur de configuration réseau
- GPIO non disponible
- Module Python manquant

### Vérifier qu'un service est bien activé

```bash
systemctl list-unit-files | grep tubpi
```

Devrait afficher :
```
tubpi-network-setup.service    enabled
tubpi-onvif-gateway.service    enabled
tubpi-webapp.service           enabled
```

## Configuration avancée

### Modifier les paramètres d'un service

1. Éditer le fichier de service :
   ```bash
   sudo nano /etc/systemd/system/tubpi-webapp.service
   ```

2. Modifier selon vos besoins (ports, chemins, options)

3. Recharger et redémarrer :
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart tubpi-webapp
   ```

### Exemples de modifications

**Changer le port de la web app :**
```ini
# Dans tubpi-webapp.service
Environment="FLASK_RUN_PORT=8080"
ExecStart=/usr/bin/python3 /opt/tubpi/src/web_app.py --port 8080
```

**Désactiver l'encodeur pour améliorer les performances :**
```ini
# Dans tubpi-onvif-gateway.service ou tubpi-webapp.service
Environment="TUBPI_DISABLE_ENCODER=1"
```

## Ordre de démarrage

Les services démarrent dans cet ordre :
1. `tubpi-network-setup` (configure le réseau)
2. `tubpi-onvif-gateway` (attend que le réseau soit configuré)
3. `tubpi-webapp` (démarre indépendamment)

Cet ordre est géré par les directives `After=` et `Before=` dans les fichiers de service.

## Logs centralisés

Pour voir tous les logs Tubpi en même temps :
```bash
sudo journalctl -u 'tubpi-*' -f
```

## Surveillance

Pour surveiller l'utilisation des ressources :
```bash
# CPU et mémoire
systemctl status tubpi-onvif-gateway

# Utilisation détaillée
systemd-cgtop

# Statistiques des services
systemctl show tubpi-webapp --property=CPUUsageNSec,MemoryCurrent
```

## Redémarrage automatique

Les services sont configurés avec `Restart=always` et `RestartSec=10`, ce qui signifie :
- Si le service plante, il redémarre automatiquement après 10 secondes
- Redémarrage illimité en cas d'échec
- Utile pour la stabilité en production

Pour désactiver le redémarrage automatique temporairement :
```bash
sudo systemctl edit tubpi-onvif-gateway
```

Ajouter :
```ini
[Service]
Restart=no
```

## Ressources

- [Documentation systemd](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Guide Raspberry Pi GPIO](https://www.raspberrypi.com/documentation/computers/os.html#gpio-and-the-40-pin-header)
- [Python systemd](https://www.freedesktop.org/software/systemd/python-systemd/)
