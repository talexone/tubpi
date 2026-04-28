#!/usr/bin/env bash
# Script d'installation des services systemd Tubpi
# Ce script installe et active les services pour qu'ils démarrent automatiquement au boot

set -euo pipefail

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Vérifier que le script est exécuté en root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Ce script doit être exécuté avec sudo ou en root.${NC}" >&2
  exit 1
fi

echo -e "${GREEN}=== Installation des services Tubpi ===${NC}\n"

# Définir les chemins
PROJECT_DIR="/opt/tubpi"
SYSTEMD_DIR="/etc/systemd/system"

# Vérifier si le projet est dans /opt/tubpi
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$CURRENT_DIR" != "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}Le projet doit être dans /opt/tubpi${NC}"
    echo -e "Voulez-vous copier le projet actuel vers /opt/tubpi ? (o/n)"
    read -r response
    if [ "$response" = "o" ] || [ "$response" = "O" ]; then
        echo -e "${GREEN}Copie du projet vers /opt/tubpi...${NC}"
        mkdir -p /opt/tubpi
        cp -r "$CURRENT_DIR"/* /opt/tubpi/
        cd /opt/tubpi
    else
        echo -e "${YELLOW}Installation annulée.${NC}"
        echo -e "Veuillez déplacer le projet vers /opt/tubpi ou créer un lien symbolique :"
        echo -e "  sudo ln -s $CURRENT_DIR /opt/tubpi"
        exit 1
    fi
fi

# Détecter l'utilisateur non-root (celui qui a lancé sudo)
if [ -n "$SUDO_USER" ]; then
    TARGET_USER="$SUDO_USER"
else
    # Si pas de SUDO_USER, chercher un utilisateur non-root existant
    for user in pi dietpi debian ubuntu; do
        if id "$user" &>/dev/null; then
            TARGET_USER="$user"
            break
        fi
    done
    if [ -z "$TARGET_USER" ]; then
        echo -e "${RED}Erreur : impossible de détecter l'utilisateur cible${NC}"
        echo -e "${YELLOW}Créez un utilisateur non-root ou définissez TARGET_USER manuellement${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Utilisateur cible détecté : ${TARGET_USER}${NC}"

# Vérifier les dépendances Python
echo -e "${GREEN}Vérification des dépendances Python...${NC}"
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo -e "${YELLOW}Installation des dépendances Python...${NC}"
    
    # Essayer d'abord les paquets système (recommandé pour Debian/DietPi)
    echo -e "  ${GREEN}→${NC} Tentative d'installation via apt..."
    apt update -qq
    # Note : Pour Raspberry Pi 5, utiliser python3-rpi-lgpio au lieu de python3-rpi.gpio
    apt install -y python3-flask python3-requests python3-rpi-lgpio 2>&1 | grep -v "already" || true
    
    # Si certains paquets manquent, essayer pip avec --break-system-packages
    echo -e "  ${GREEN}→${NC} Vérification des paquets manquants..."
    # Pour Raspberry Pi 5, vérifier lgpio (rpi-lgpio fournit l'API RPi.GPIO via lgpio)
    if ! python3 -c "import flask" 2>/dev/null || \
       ! python3 -c "import requests" 2>/dev/null || \
       ! python3 -c "import RPi.GPIO" 2>/dev/null; then
        echo -e "  ${YELLOW}→${NC} Installation via pip (--break-system-packages)..."
        pip3 install --break-system-packages -r "$PROJECT_DIR/requirements.txt" 2>&1 | grep -v "Requirement already satisfied" || true
    else
        echo -e "  ${GREEN}✓${NC} Toutes les dépendances sont installées"
    fi
else
    echo -e "${YELLOW}Attention : requirements.txt non trouvé${NC}"
fi

# Rendre les scripts exécutables
echo -e "${GREEN}Configuration des permissions des scripts...${NC}"
if [ -f "$PROJECT_DIR/setup_camera_gateway.sh" ]; then
    chmod +x "$PROJECT_DIR/setup_camera_gateway.sh"
    echo -e "  ${GREEN}✓${NC} setup_camera_gateway.sh rendu exécutable"
else
    echo -e "  ${YELLOW}○${NC} setup_camera_gateway.sh non trouvé"
fi

# Vérifier les permissions GPIO pour l'utilisateur cible
echo -e "${GREEN}Configuration des permissions GPIO...${NC}"
if ! groups "$TARGET_USER" | grep -q gpio; then
    usermod -a -G gpio "$TARGET_USER"
    echo -e "${GREEN}✓ Utilisateur '$TARGET_USER' ajouté au groupe 'gpio'${NC}"
else
    echo -e "${GREEN}✓ Utilisateur '$TARGET_USER' déjà dans le groupe 'gpio'${NC}"
fi

# Configuration des permissions GPIO pour Raspberry Pi 5
echo -e "${GREEN}Configuration des permissions GPIO (Raspberry Pi 5)...${NC}"
if [ -f "$PROJECT_DIR/systemd/99-gpio.rules" ]; then
    cp "$PROJECT_DIR/systemd/99-gpio.rules" /etc/udev/rules.d/
    echo -e "  ${GREEN}✓${NC} Règle udev GPIO installée"
    
    # Recharger les règles udev
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Règles udev rechargées"
else
    echo -e "  ${YELLOW}○${NC} Fichier 99-gpio.rules non trouvé"
fi

# Vérifier et corriger les permissions des devices GPIO
if [ -e /dev/gpiochip0 ]; then
    chown root:gpio /dev/gpiochip* 2>/dev/null || true
    chmod 660 /dev/gpiochip* 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Permissions /dev/gpiochip* configurées"
fi

if [ -e /dev/gpiomem ]; then
    chown root:gpio /dev/gpiomem 2>/dev/null || true
    chmod 660 /dev/gpiomem 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Permissions /dev/gpiomem configurées"
fi

# Configuration des credentials de la caméra
echo -e "\n${GREEN}Configuration des credentials de la caméra...${NC}"
if [ ! -f "$PROJECT_DIR/camera.res" ]; then
    echo -e "${YELLOW}Le fichier camera.res n'existe pas.${NC}"
    echo -e "${YELLOW}Ce fichier contient les identifiants pour accéder à la caméra ONVIF.${NC}"
    echo -e ""
    read -p "Nom d'utilisateur de la caméra [admin]: " camera_user
    camera_user=${camera_user:-admin}
    
    read -s -p "Mot de passe de la caméra: " camera_password
    echo ""
    
    if [ -z "$camera_password" ]; then
        echo -e "${RED}Erreur: Le mot de passe ne peut pas être vide${NC}"
        exit 1
    fi
    
    # Créer le fichier camera.res
    cat > "$PROJECT_DIR/camera.res" << EOF
# Configuration des credentials de la caméra ONVIF
# Généré automatiquement par install_services.sh

user=$camera_user
password=$camera_password
EOF
    
    chmod 640 "$PROJECT_DIR/camera.res"
    chown root:$TARGET_USER "$PROJECT_DIR/camera.res"
    echo -e "  ${GREEN}✓${NC} Fichier camera.res créé"
else
    echo -e "  ${GREEN}✓${NC} Fichier camera.res déjà existant"
    # Vérifier les permissions
    chmod 640 "$PROJECT_DIR/camera.res"
    chown root:$TARGET_USER "$PROJECT_DIR/camera.res"
    echo -e "  ${GREEN}✓${NC} Permissions camera.res configurées (640, root:$TARGET_USER)"
fi

# Copier les fichiers de service et adapter l'utilisateur
echo -e "\n${GREEN}Installation des fichiers de service systemd...${NC}"

services=(
    "tubpi-network-setup"
    "tubpi-onvif-gateway"
    "tubpi-webapp"
)

for service in "${services[@]}"; do
    if [ -f "$PROJECT_DIR/systemd/${service}.service" ]; then
        echo -e "  ${GREEN}→${NC} Installation de ${service}.service"
        
        # Copier et adapter l'utilisateur dans le service webapp
        if [ "$service" = "tubpi-webapp" ]; then
            sed "s/User=pi/User=$TARGET_USER/g" "$PROJECT_DIR/systemd/${service}.service" > "$SYSTEMD_DIR/${service}.service"
        else
            cp "$PROJECT_DIR/systemd/${service}.service" "$SYSTEMD_DIR/"
        fi
        
        chmod 644 "$SYSTEMD_DIR/${service}.service"
    else
        echo -e "  ${RED}✗${NC} Fichier ${service}.service non trouvé"
        exit 1
    fi
done

# Recharger systemd
echo -e "\n${GREEN}Rechargement de systemd...${NC}"
systemctl daemon-reload

# Activer et démarrer les services
echo -e "\n${GREEN}Activation des services...${NC}"

# Demander quels services activer
echo -e "\n${YELLOW}Quels services voulez-vous activer ?${NC}"
echo -e "1) Tous les services (recommandé)"
echo -e "2) Uniquement ONVIF Gateway (port 80)"
echo -e "3) Uniquement Web App (port 5000)"
echo -e "4) ONVIF Gateway + Web App (pas de configuration réseau)"
echo -e "5) Configuration personnalisée"
read -r choice

case $choice in
    1)
        services_to_enable=("tubpi-network-setup" "tubpi-onvif-gateway" "tubpi-webapp")
        ;;
    2)
        services_to_enable=("tubpi-onvif-gateway")
        ;;
    3)
        services_to_enable=("tubpi-webapp")
        ;;
    4)
        services_to_enable=("tubpi-onvif-gateway" "tubpi-webapp")
        ;;
    5)
        echo -e "${YELLOW}Configuration personnalisée :${NC}"
        services_to_enable=()
        for service in "${services[@]}"; do
            echo -n "Activer ${service} ? (o/n) : "
            read -r response
            if [ "$response" = "o" ] || [ "$response" = "O" ]; then
                services_to_enable+=("$service")
            fi
        done
        ;;
    *)
        echo -e "${RED}Choix invalide${NC}"
        exit 1
        ;;
esac

# Activer et démarrer les services sélectionnés
for service in "${services_to_enable[@]}"; do
    echo -e "\n${GREEN}→ Activation de ${service}...${NC}"
    systemctl enable "${service}.service"
    echo -e "  ${GREEN}✓${NC} Service activé (démarrera au boot)"
done

# Demander si on démarre maintenant
echo -e "\n${YELLOW}Voulez-vous démarrer les services maintenant ? (o/n)${NC}"
read -r start_now

if [ "$start_now" = "o" ] || [ "$start_now" = "O" ]; then
    for service in "${services_to_enable[@]}"; do
        echo -e "${GREEN}→ Démarrage de ${service}...${NC}"
        if systemctl start "${service}.service"; then
            echo -e "  ${GREEN}✓${NC} Service démarré"
        else
            echo -e "  ${RED}✗${NC} Erreur lors du démarrage (voir: journalctl -u ${service})"
        fi
    done
fi

# Afficher l'état des services
echo -e "\n${GREEN}=== État des services ===${NC}"
for service in "${services_to_enable[@]}"; do
    echo -e "\n${YELLOW}${service}:${NC}"
    systemctl status "${service}.service" --no-pager -l | head -10 || true
done

# Instructions finales
echo -e "\n${GREEN}=== Installation terminée ===${NC}\n"
echo -e "${YELLOW}Commandes utiles :${NC}"
echo -e "  • Voir les logs : ${GREEN}sudo journalctl -u tubpi-onvif-gateway -f${NC}"
echo -e "  • Voir les logs : ${GREEN}sudo journalctl -u tubpi-webapp -f${NC}"
echo -e "  • Redémarrer    : ${GREEN}sudo systemctl restart tubpi-onvif-gateway${NC}"
echo -e "  • Arrêter       : ${GREEN}sudo systemctl stop tubpi-webapp${NC}"
echo -e "  • État          : ${GREEN}sudo systemctl status tubpi-onvif-gateway${NC}"
echo -e "  • Désactiver    : ${GREEN}sudo systemctl disable tubpi-webapp${NC}"
echo -e "\n${YELLOW}Les services démarreront automatiquement au prochain redémarrage.${NC}"
echo -e "\n${GREEN}Accès aux interfaces :${NC}"
echo -e "  • ONVIF Gateway : ${GREEN}http://<ip-raspberry>:80${NC}"
echo -e "  • Web App       : ${GREEN}http://<ip-raspberry>:5000${NC}"

# Avertissement si le réseau setup est activé
if [[ " ${services_to_enable[*]} " =~ " tubpi-network-setup " ]]; then
    echo -e "\n${RED}⚠️  ATTENTION : Le service de configuration réseau est activé${NC}"
    echo -e "${YELLOW}Cela modifiera la configuration réseau à chaque démarrage.${NC}"
    echo -e "${YELLOW}Vérifiez le fichier setup_camera_gateway.sh pour les détails.${NC}"
fi
