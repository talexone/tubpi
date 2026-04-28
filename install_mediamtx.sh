#!/bin/bash
# Script d'installation de MediaMTX pour le streaming WebRTC

set -e

echo "================================================"
echo "  Installation de MediaMTX"
echo "================================================"

# Vérifier que le script est exécuté en tant que root
if [ "$EUID" -ne 0 ]; then 
    echo "Erreur: Ce script doit être exécuté en tant que root"
    echo "Utilisez: sudo $0"
    exit 1
fi

# Version de MediaMTX
MEDIAMTX_VERSION="v1.9.4"

# Détection de l'architecture
ARCH=$(uname -m)
case "$ARCH" in
    aarch64|arm64)
        MEDIAMTX_ARCH="arm64v8"
        ;;
    armv7l|armhf)
        MEDIAMTX_ARCH="armv7"
        ;;
    x86_64|amd64)
        MEDIAMTX_ARCH="amd64"
        ;;
    *)
        echo "Erreur: Architecture non supportée: $ARCH"
        exit 1
        ;;
esac

echo ""
echo "Configuration détectée:"
echo "  Architecture: $ARCH → $MEDIAMTX_ARCH"
echo "  Version: $MEDIAMTX_VERSION"
echo ""

# URLs de téléchargement
MEDIAMTX_URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_${MEDIAMTX_ARCH}.tar.gz"

# Créer le répertoire d'installation
echo "Création du répertoire /opt/mediamtx..."
mkdir -p /opt/mediamtx
cd /opt/mediamtx

# Télécharger MediaMTX
echo "Téléchargement de MediaMTX..."
if command -v wget &> /dev/null; then
    wget -q --show-progress -O mediamtx.tar.gz "$MEDIAMTX_URL"
elif command -v curl &> /dev/null; then
    curl -L -o mediamtx.tar.gz "$MEDIAMTX_URL"
else
    echo "Erreur: wget ou curl requis"
    exit 1
fi

# Extraire l'archive
echo "Extraction..."
tar -xzf mediamtx.tar.gz
rm mediamtx.tar.gz

# Rendre le binaire exécutable
chmod +x /opt/mediamtx/mediamtx

# Vérifier l'installation
if [ -x /opt/mediamtx/mediamtx ]; then
    echo "✓ MediaMTX installé: $(/opt/mediamtx/mediamtx --version 2>&1 | head -1)"
else
    echo "✗ Erreur: Le binaire MediaMTX n'est pas exécutable"
    exit 1
fi

# Copier le script de mise à jour de configuration
echo "Installation du script de configuration..."
if [ -f /opt/tubpi/update_mediamtx_config.sh ]; then
    cp /opt/tubpi/update_mediamtx_config.sh /opt/mediamtx/update_config.sh
    chmod +x /opt/mediamtx/update_config.sh
    echo "✓ Script de configuration copié"
else
    echo "⚠ Attention: /opt/tubpi/update_mediamtx_config.sh introuvable"
    echo "  Créez-le manuellement ou copiez-le depuis le dépôt"
fi

# Générer la configuration initiale
if [ -x /opt/mediamtx/update_config.sh ]; then
    echo "Génération de la configuration initiale..."
    /opt/mediamtx/update_config.sh
    echo "✓ Configuration générée"
else
    echo "⚠ Configuration non générée (script update_config.sh manquant)"
fi

# Copier et installer le service systemd
echo "Installation du service systemd..."
if [ -f /opt/tubpi/systemd/mediamtx.service ]; then
    cp /opt/tubpi/systemd/mediamtx.service /etc/systemd/system/
    systemctl daemon-reload
    echo "✓ Service systemd installé"
else
    echo "⚠ Attention: /opt/tubpi/systemd/mediamtx.service introuvable"
fi

# Demander si on active et démarre le service
echo ""
read -p "Voulez-vous activer et démarrer le service MediaMTX? (o/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[OoYy]$ ]]; then
    systemctl enable mediamtx
    systemctl start mediamtx
    
    sleep 2
    
    if systemctl is-active --quiet mediamtx; then
        echo "✓ Service MediaMTX démarré avec succès"
        echo ""
        echo "Vérification de l'état:"
        systemctl status mediamtx --no-pager -l
    else
        echo "✗ Erreur: Le service MediaMTX n'a pas démarré"
        echo ""
        echo "Logs d'erreur:"
        journalctl -u mediamtx -n 20 --no-pager
        exit 1
    fi
else
    echo "Service non démarré. Pour le démarrer manuellement:"
    echo "  sudo systemctl enable mediamtx"
    echo "  sudo systemctl start mediamtx"
fi

echo ""
echo "================================================"
echo "  Installation terminée!"
echo "================================================"
echo ""
echo "Commandes utiles:"
echo "  systemctl status mediamtx     - Voir l'état du service"
echo "  journalctl -u mediamtx -f     - Voir les logs en temps réel"
echo "  systemctl restart mediamtx    - Redémarrer le service"
echo ""
echo "URLs d'accès:"
echo "  Interface web: http://$(hostname -I | awk '{print $1}'):8889/"
echo "  API: http://$(hostname -I | awk '{print $1}'):8889/v3/config/paths/list"
echo "  Flux WebRTC: http://$(hostname -I | awk '{print $1}'):8889/ma_camera"
echo ""
