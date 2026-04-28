#!/bin/bash
# Script pour mettre à jour la configuration MediaMTX avec les credentials de la caméra

CAMERA_RES="/opt/tubpi/camera.res"
MEDIAMTX_CONFIG="/opt/mediamtx/mediamtx.yml"
CAMERA_IP="192.168.1.108"
CAMERA_PORT="554"
STREAM_PATH="/cam/realmonitor?channel=1&subtype=1"

# Vérifier que camera.res existe
if [ ! -f "$CAMERA_RES" ]; then
    echo "Erreur: $CAMERA_RES introuvable"
    exit 1
fi

# Lire les credentials
USER=$(grep "^user=" "$CAMERA_RES" | cut -d= -f2)
PASSWORD=$(grep "^password=" "$CAMERA_RES" | cut -d= -f2)

if [ -z "$USER" ] || [ -z "$PASSWORD" ]; then
    echo "Erreur: Impossible de lire user ou password depuis $CAMERA_RES"
    exit 1
fi

echo "Génération de la configuration MediaMTX..."

# Générer la configuration
cat > "$MEDIAMTX_CONFIG" << EOF
# MediaMTX configuration
# Auto-généré par update_config.sh - NE PAS ÉDITER MANUELLEMENT

# API HTTP
api: yes
apiAddress: :8889

# WebRTC
webrtc: yes
webrtcAddress: :8889

# Logs
logLevel: info
logDestinations: [stdout]
logFile: /var/log/mediamtx.log

# Paths (flux vidéo)
paths:
  # Flux caméra principal
  ma_camera:
    source: rtsp://${USER}:${PASSWORD}@${CAMERA_IP}:${CAMERA_PORT}${STREAM_PATH}
    sourceProtocol: automatic
    sourceOnDemand: yes
    runOnDemand: echo "Stream ma_camera started"
    runOnDemandCloseAfter: 10s
    
  # Flux haute qualité (optionnel)
  ma_camera_hq:
    source: rtsp://${USER}:${PASSWORD}@${CAMERA_IP}:${CAMERA_PORT}/cam/realmonitor?channel=1&subtype=0
    sourceProtocol: automatic
    sourceOnDemand: yes
    runOnDemand: echo "Stream ma_camera_hq started"
    runOnDemandCloseAfter: 10s
EOF

# Sécuriser le fichier (contient des credentials)
chmod 640 "$MEDIAMTX_CONFIG"
chown root:root "$MEDIAMTX_CONFIG"

echo "Configuration MediaMTX générée avec succès"
echo "  Flux: ma_camera (subtype=1 - qualité moyenne)"
echo "  Flux HQ: ma_camera_hq (subtype=0 - haute qualité)"
echo "  API/WebRTC: http://localhost:8889"
