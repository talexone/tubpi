# Configuration MediaMTX pour streaming WebRTC

La webapp utilise MediaMTX pour diffuser le flux de la caméra RTSP en WebRTC.

## Installation

### Méthode automatique (recommandée)

```bash
cd /opt/tubpi
sudo chmod +x install_mediamtx.sh
sudo ./install_mediamtx.sh
```

Ce script:
- Détecte votre architecture (ARM64, ARM, x86_64)
- Télécharge MediaMTX v1.9.4
- Installe dans `/opt/mediamtx/`
- Copie le script de configuration
- Génère la configuration avec credentials depuis `camera.res`
- Installe et démarre le service systemd

### Méthode manuelle

```bash
# 1. Télécharger MediaMTX pour votre architecture
cd /opt
sudo mkdir -p mediamtx
cd mediamtx

# Pour Raspberry Pi 5 (ARM64)
sudo wget https://github.com/bluenviron/mediamtx/releases/download/v1.18.0/mediamtx_v1.18.0_linux_arm64.tar.gz
sudo tar -xzf mediamtx_v1.18.0_linux_arm64.tar.gz
sudo rm mediamtx_v1.18.0_linux_arm64.tar.gz

# 2. Copier le script de mise à jour
sudo cp /opt/tubpi/update_mediamtx_config.sh /opt/mediamtx/update_config.sh
sudo chmod +x /opt/mediamtx/update_config.sh

# 3. Générer la configuration
sudo /opt/mediamtx/update_config.sh

# 4. Installer le service systemd
sudo cp /opt/tubpi/systemd/mediamtx.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
```

## Configuration

MediaMTX est configuré automatiquement via le script `update_config.sh` qui:
1. Lit les credentials depuis `/opt/tubpi/camera.res`
2. Génère `/opt/mediamtx/mediamtx.yml` avec les bons paramètres

### Fichier de configuration généré

Le fichier `/opt/mediamtx/mediamtx.yml` contient:

```yaml
# API et interface web
api: yes
apiAddress: :8889

# Activer WebRTC
webrtc: yes
webrtcAddress: :8889

# Configuration du flux
paths:
  ma_camera:
    source: rtsp://USER:PASSWORD@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1
    sourceProtocol: automatic
    sourceOnDemand: yes
  ma_camera_hq:
    source: rtsp://USER:PASSWORD@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0
    sourceProtocol: automatic
    sourceOnDemand: yes
```

**Note**: Les credentials sont automatiquement injectés depuis `/opt/tubpi/camera.res`

### Modifier la configuration manuellement

Si vous devez modifier la configuration:

```bash
# Éditer le script de mise à jour
sudo nano /opt/mediamtx/update_config.sh

# Régénérer la configuration
sudo /opt/mediamtx/update_config.sh

# Redémarrer MediaMTX
sudo systemctl restart mediamtx
```

## Vérification

### 1. Vérifier que MediaMTX tourne

```bash
sudo systemctl status mediamtx
```

### 2. Tester l'API

```bash
curl http://localhost:8889/v3/config/paths/list
```

Devrait retourner la liste des flux incluant `ma_camera` et `ma_camera_hq`.

### 3. Tester le flux WebRTC

Ouvrir dans un navigateur:
```
http://192.168.66.212:8889/ma_camera
```

MediaMTX devrait afficher une page avec le lecteur WebRTC intégré.

### 4. Vérifier les logs

```bash
sudo journalctl -u mediamtx -f
```

Chercher les lignes comme:
```
[ma_camera] ready
[ma_camera] requesting [rtsp://...]
```

## Intégration avec la webapp

La webapp (port 5000) se connecte automatiquement à MediaMTX (port 8889) via WebRTC:

1. La page charge l'URL RTSP depuis `/camera/rtsp-url`
2. JavaScript établit une connexion WebRTC à `http://192.168.66.212:8889/ma_camera/whep`
3. MediaMTX retourne le flux converti en WebRTC
4. Le navigateur affiche le flux dans l'élément `<video>`

## Ports utilisés

- **8889** - API HTTP et WebRTC de MediaMTX
- **5000** - Webapp Flask

Assurez-vous que ces ports sont accessibles depuis le navigateur client.

## Dépannage

### Le flux ne s'affiche pas

1. Vérifier que MediaMTX a accès à la caméra:
```bash
curl -v "rtsp://admin:password@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1"
```

2. Vérifier la console JavaScript du navigateur (F12) pour les erreurs WebRTC

3. Tester directement via l'interface MediaMTX: `http://192.168.66.212:8889/ma_camera`

### Erreur de connexion WebRTC

- Vérifier que `webrtc: yes` dans la config MediaMTX
- Vérifier que le port 8889 n'est pas bloqué par le firewall
- Regarder les logs MediaMTX pour voir les erreurs de connexion

### Qualité vidéo

MediaMTX propose deux flux:
- **ma_camera** - Flux qualité moyenne (subtype=1) pour économiser la bande passante
- **ma_camera_hq** - Flux haute qualité (subtype=0) pour une meilleure image

Pour un flux basse latence, ajuster dans `/opt/mediamtx/update_config.sh`:
```yaml
paths:
  ma_camera:
    source: rtsp://...
    sourceProtocol: tcp
    rtspTransport: tcp
```

## Structure des fichiers

```
/opt/mediamtx/
├── mediamtx              # Binaire exécutable
├── mediamtx.yml          # Configuration (générée automatiquement)
├── update_config.sh      # Script de mise à jour de configuration
└── mediamtx.yml.bak     # Sauvegarde automatique

/opt/tubpi/
├── camera.res                    # Credentials de la caméra
├── update_mediamtx_config.sh     # Script source de configuration
├── install_mediamtx.sh           # Script d'installation
└── systemd/
    └── mediamtx.service          # Service systemd

/etc/systemd/system/
└── mediamtx.service              # Service installé
```

## Mise à jour

Pour mettre à jour MediaMTX vers une nouvelle version:

1. Éditer `install_mediamtx.sh` et changer `MEDIAMTX_VERSION`
2. Arrêter le service: `sudo systemctl stop mediamtx`
3. Réexécuter l'installation: `sudo ./install_mediamtx.sh`
4. Redémarrer: `sudo systemctl start mediamtx`

## Désinstallation

```bash
# Arrêter et désactiver le service
sudo systemctl stop mediamtx
sudo systemctl disable mediamtx

# Supprimer les fichiers
sudo rm /etc/systemd/system/mediamtx.service
sudo rm -rf /opt/mediamtx

# Recharger systemd
sudo systemctl daemon-reload
```
