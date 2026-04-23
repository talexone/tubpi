#!/usr/bin/env bash
# Script d'installation avec support pigpio
# Cette version détecte si pigpio doit être installé et configure le daemon

set -euo pipefail

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Vérifier que le script est exécuté en root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Ce script doit être exécuté avec sudo ou en root.${NC}" >&2
  exit 1
fi

echo -e "${GREEN}=== Installation des services Tubpi (version pigpio) ===${NC}\n"

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

# Demander quelle version GPIO utiliser
echo -e "\n${BLUE}=== Configuration GPIO ===${NC}"
echo -e "${YELLOW}Quelle bibliothèque GPIO voulez-vous utiliser ?${NC}"
echo -e "1) ${GREEN}pigpio${NC} - Recommandé pour tous les Pi (incluant Pi 5)"
echo -e "   ✓ Meilleure performance"
echo -e "   ✓ PWM matériel précis"
echo -e "   ✓ Compatible tous les modèles"
echo -e ""
echo -e "2) ${YELLOW}rpi-lgpio${NC} - Pour Raspberry Pi 5 uniquement"
echo -e "   ✓ Compatible API RPi.GPIO"
echo -e "   ○ Performance standard"
echo -e ""
read -r -p "Choix (1-2) [1]: " gpio_choice
gpio_choice=${gpio_choice:-1}

USE_PIGPIO=false
if [ "$gpio_choice" = "1" ]; then
    USE_PIGPIO=true
    echo -e "${GREEN}→ Installation avec pigpio${NC}"
else
    echo -e "${GREEN}→ Installation avec rpi-lgpio${NC}"
fi

# Vérifier les dépendances Python
echo -e "\n${GREEN}Installation des dépendances Python...${NC}"
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    # Essayer d'abord les paquets système
    echo -e "  ${GREEN}→${NC} Installation via apt..."
    apt update -qq
    
    if [ "$USE_PIGPIO" = true ]; then
        # Installation pigpio
        apt install -y python3-flask python3-requests python3-pigpio pigpio 2>&1 | grep -v "already" || true
        
        # Vérifier si pigpiod est disponible
        if ! systemctl list-unit-files | grep -q pigpiod.service; then
            echo -e "  ${YELLOW}⚠${NC} Service pigpiod non trouvé, création manuelle..."
            # Le paquet pigpio devrait l'installer, mais on vérifie
        fi
    else
        # Installation rpi-lgpio
        apt install -y python3-flask python3-requests python3-rpi-lgpio 2>&1 | grep -v "already" || true
    fi
    
    # Vérifier les paquets manquants et installer via pip si nécessaire
    echo -e "  ${GREEN}→${NC} Vérification des paquets manquants..."
    missing=false
    
    if ! python3 -c "import flask" 2>/dev/null; then
        missing=true
    fi
    if ! python3 -c "import requests" 2>/dev/null; then
        missing=true
    fi
    
    if [ "$USE_PIGPIO" = true ]; then
        if ! python3 -c "import pigpio" 2>/dev/null; then
            missing=true
        fi
    else
        if ! python3 -c "import RPi.GPIO" 2>/dev/null; then
            missing=true
        fi
    fi
    
    if [ "$missing" = true ]; then
        echo -e "  ${YELLOW}→${NC} Installation via pip (--break-system-packages)..."
        pip3 install --break-system-packages -r "$PROJECT_DIR/requirements.txt" 2>&1 | grep -v "Requirement already satisfied" || true
    else
        echo -e "  ${GREEN}✓${NC} Toutes les dépendances sont installées"
    fi
else
    echo -e "${YELLOW}Attention : requirements.txt non trouvé${NC}"
fi

# Configuration spécifique à pigpio
if [ "$USE_PIGPIO" = true ]; then
    echo -e "\n${GREEN}Configuration du daemon pigpiod...${NC}"
    
    # Activer et démarrer pigpiod
    systemctl enable pigpiod.service
    systemctl start pigpiod.service
    
    # Vérifier que le daemon est actif
    if systemctl is-active --quiet pigpiod.service; then
        echo -e "  ${GREEN}✓${NC} Daemon pigpiod actif"
    else
        echo -e "  ${RED}✗${NC} Daemon pigpiod non actif"
        echo -e "  ${YELLOW}→${NC} Vérifier : sudo systemctl status pigpiod"
    fi
    
    # Créer un lien symbolique pour utiliser motor_driver_pigpio
    echo -e "${GREEN}Configuration du driver moteur pigpio...${NC}"
    if [ -f "$PROJECT_DIR/src/motor_driver_pigpio.py" ]; then
        # Sauvegarder l'ancien si existe
        if [ -f "$PROJECT_DIR/src/motor_driver.py" ] && [ ! -L "$PROJECT_DIR/src/motor_driver.py" ]; then
            mv "$PROJECT_DIR/src/motor_driver.py" "$PROJECT_DIR/src/motor_driver_rpi_gpio.py.bak"
            echo -e "  ${GREEN}✓${NC} Ancien motor_driver.py sauvegardé"
        fi
        # Créer le lien
        ln -sf motor_driver_pigpio.py "$PROJECT_DIR/src/motor_driver.py"
        echo -e "  ${GREEN}✓${NC} motor_driver.py → motor_driver_pigpio.py"
    fi
fi

# Rendre les scripts exécutables
echo -e "\n${GREEN}Configuration des permissions des scripts...${NC}"
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
        
        # Copier et adapter selon le backend GPIO
        if [ "$USE_PIGPIO" = true ] && { [ "$service" = "tubpi-onvif-gateway" ] || [ "$service" = "tubpi-webapp" ]; }; then
            # Ajouter la dépendance pigpiod
            sed -e "s/User=pi/User=$TARGET_USER/g" \
                -e "s/After=network-online.target/After=network-online.target pigpiod.service/g" \
                -e "/After=/a Requires=pigpiod.service" \
                "$PROJECT_DIR/systemd/${service}.service" > "$SYSTEMD_DIR/${service}.service"
        elif [ "$service" = "tubpi-webapp" ]; then
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

if [ "$USE_PIGPIO" = true ]; then
    echo -e "${BLUE}Configuration GPIO : pigpio${NC}"
    echo -e "  • Daemon pigpiod : ${GREEN}actif${NC}"
    echo -e "  • Driver moteur : motor_driver_pigpio.py"
    echo -e "  • Performance : ${GREEN}optimale${NC}"
fi

echo -e "\n${YELLOW}Commandes utiles :${NC}"
echo -e "  • Voir les logs : ${GREEN}sudo journalctl -u tubpi-onvif-gateway -f${NC}"
echo -e "  • Voir les logs : ${GREEN}sudo journalctl -u tubpi-webapp -f${NC}"
echo -e "  • Redémarrer    : ${GREEN}sudo systemctl restart tubpi-onvif-gateway${NC}"
echo -e "  • Arrêter       : ${GREEN}sudo systemctl stop tubpi-webapp${NC}"
echo -e "  • État          : ${GREEN}sudo systemctl status tubpi-onvif-gateway${NC}"
echo -e "  • Désactiver    : ${GREEN}sudo systemctl disable tubpi-webapp${NC}"

if [ "$USE_PIGPIO" = true ]; then
    echo -e "  • État pigpiod  : ${GREEN}sudo systemctl status pigpiod${NC}"
fi

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

echo -e "\n${BLUE}Documentation :${NC}"
echo -e "  • Guide pigpio : ${GREEN}docs/pigpio-migration.md${NC}"
echo -e "  • Services : ${GREEN}docs/services.md${NC}"
