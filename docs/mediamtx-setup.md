# Configuration MediaMTX pour streaming WebRTC

La webapp utilise MediaMTX (déjà installé sur le Raspberry Pi) pour diffuser le flux de la caméra RTSP en WebRTC.

## Configuration requise

MediaMTX doit être configuré pour:
1. Lire le flux RTSP de la caméra
2. Exposer ce flux via WebRTC sur le port 8889
3. Utiliser le protocole WHEP (WebRTC-HTTP Egress Protocol)

### Fichier de configuration MediaMTX

Éditer `/etc/mediamtx/mediamtx.yml` (ou le chemin de configuration utilisé):

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
    source: rtsp://admin:password@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1
    sourceProtocol: automatic
    sourceOnDemand: yes
    runOnDemand: echo "Stream started"
```

### Variables à adapter

Remplacer dans la configuration:
- `admin:password` par les vraies credentials de la caméra (lire depuis `/opt/tubpi/camera.res`)
- `192.168.1.108` par l'IP de la caméra
- `ma_camera` doit correspondre au nom de flux dans la webapp (déjà configuré)

## Script de mise à jour automatique

Pour générer automatiquement la configuration MediaMTX depuis `/opt/tubpi/camera.res`:

```bash
#!/bin/bash
# update_mediamtx_config.sh

CAMERA_RES="/opt/tubpi/camera.res"
MEDIAMTX_CONFIG="/etc/mediamtx/mediamtx.yml"
CAMERA_IP="192.168.1.108"
CAMERA_PORT="554"
STREAM_PATH="/cam/realmonitor?channel=1&subtype=1"

# Lire les credentials
USER=$(grep "^user=" "$CAMERA_RES" | cut -d= -f2)
PASSWORD=$(grep "^password=" "$CAMERA_RES" | cut -d= -f2)

# Générer la configuration
cat > "$MEDIAMTX_CONFIG" << EOF
api: yes
apiAddress: :8889

webrtc: yes
webrtcAddress: :8889
webrtcServerKey: server.key
webrtcServerCert: server.crt

paths:
  ma_camera:
    source: rtsp://${USER}:${PASSWORD}@${CAMERA_IP}:${CAMERA_PORT}${STREAM_PATH}
    sourceProtocol: automatic
    sourceOnDemand: yes
EOF

chmod 640 "$MEDIAMTX_CONFIG"
echo "Configuration MediaMTX mise à jour"
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

Devrait retourner la liste des flux incluant `ma_camera`.

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

Pour un flux haute qualité, utiliser `subtype=0` (stream principal) au lieu de `subtype=1` (sous-stream).

Pour un flux basse latence, ajuster dans MediaMTX:
```yaml
paths:
  ma_camera:
    source: rtsp://...
    sourceProtocol: tcp
    rtspTransport: tcp
```
