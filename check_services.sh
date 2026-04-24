#!/usr/bin/env bash
# Script de vérification de l'état des services Tubpi

set -euo pipefail

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Vérification des services Tubpi ===${NC}\n"

services=(
    "tubpi-network-setup"
    "tubpi-onvif-gateway"
    "tubpi-webapp"
)

check_service() {
    local service=$1
    local service_file="/etc/systemd/system/${service}.service"
    
    echo -e "${YELLOW}${service}${NC}"
    
    # Vérifier si le fichier existe
    if [ ! -f "$service_file" ]; then
        echo -e "  ${RED}✗${NC} Service non installé"
        return 1
    fi
    echo -e "  ${GREEN}✓${NC} Fichier de service présent"
    
    # Vérifier si activé
    if systemctl is-enabled --quiet "${service}.service" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Activé (démarre au boot)"
    else
        echo -e "  ${YELLOW}○${NC} Non activé (ne démarre pas au boot)"
    fi
    
    # Vérifier si actif
    if systemctl is-active --quiet "${service}.service"; then
        echo -e "  ${GREEN}✓${NC} En cours d'exécution"
        
        # Afficher depuis combien de temps
        uptime=$(systemctl show "${service}.service" -p ActiveEnterTimestamp --value)
        if [ -n "$uptime" ]; then
            echo -e "  ${BLUE}ℹ${NC} Démarré : $uptime"
        fi
    else
        echo -e "  ${RED}✗${NC} Arrêté"
        
        # Vérifier s'il a échoué
        if systemctl is-failed --quiet "${service}.service"; then
            echo -e "  ${RED}✗${NC} État : ÉCHEC"
            echo -e "  ${YELLOW}→${NC} Voir les logs : sudo journalctl -u ${service} -n 20"
        fi
    fi
    
    echo ""
}

# Vérifier chaque service
all_ok=true
for service in "${services[@]}"; do
    if ! check_service "$service"; then
        all_ok=false
    fi
done

# Tests de connectivité
echo -e "${BLUE}=== Tests de connectivité ===${NC}\n"

# Test port 80 (ONVIF Gateway)
echo -e "${YELLOW}Port 80 (ONVIF Gateway)${NC}"
if systemctl is-active --quiet tubpi-onvif-gateway.service; then
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:80 >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Port 80 accessible"
    else
        echo -e "  ${YELLOW}○${NC} Port 80 non accessible (peut être normal si pas de route par défaut)"
    fi
else
    echo -e "  ${YELLOW}○${NC} Service non démarré"
fi
echo ""

# Test port 5000 (Web App)
echo -e "${YELLOW}Port 5000 (Web App)${NC}"
if systemctl is-active --quiet tubpi-webapp.service; then
    if curl -s -o /dev/null http://localhost:5000 >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Port 5000 accessible"
    else
        echo -e "  ${RED}✗${NC} Port 5000 non accessible"
    fi
else
    echo -e "  ${YELLOW}○${NC} Service non démarré"
fi
echo ""

# Vérification GPIO
echo -e "${BLUE}=== Vérification GPIO ===${NC}\n"

# Détecter l'utilisateur non-root
TARGET_USER=""
if [ -n "$SUDO_USER" ]; then
    TARGET_USER="$SUDO_USER"
else
    for user in pi dietpi debian ubuntu; do
        if id "$user" &>/dev/null; then
            TARGET_USER="$user"
            break
        fi
    done
fi

echo -e "${YELLOW}Permissions GPIO${NC}"
if [ -n "$TARGET_USER" ]; then
    if groups "$TARGET_USER" | grep -q gpio; then
        echo -e "  ${GREEN}✓${NC} Utilisateur '$TARGET_USER' dans le groupe 'gpio'"
    else
        echo -e "  ${RED}✗${NC} Utilisateur '$TARGET_USER' PAS dans le groupe 'gpio'"
        echo -e "  ${YELLOW}→${NC} Exécuter : sudo usermod -a -G gpio $TARGET_USER"
    fi
else
    echo -e "  ${YELLOW}○${NC} Impossible de détecter l'utilisateur non-root"
fi

# Vérifier les devices GPIO
if ls /dev/gpiochip* &>/dev/null 2>&1; then
    echo -e "${YELLOW}Devices GPIO (Raspberry Pi 5)${NC}"
    all_gpio_ok=true
    for dev in /dev/gpiochip*; do
        group=$(ls -l "$dev" | awk '{print $4}')
        if [ "$group" = "gpio" ]; then
            echo -e "  ${GREEN}✓${NC} $dev (groupe: gpio)"
        else
            echo -e "  ${RED}✗${NC} $dev (groupe: $group - devrait être gpio)"
            all_gpio_ok=false
        fi
    done
    if [ "$all_gpio_ok" = false ]; then
        echo -e "  ${YELLOW}→${NC} Corriger : sudo chown root:gpio /dev/gpiochip* && sudo chmod 660 /dev/gpiochip*"
        echo -e "  ${YELLOW}→${NC} Installer règle udev : sudo cp /opt/tubpi/systemd/99-gpio.rules /etc/udev/rules.d/"
    fi
elif [ -e /dev/gpiomem ]; then
    echo -e "${YELLOW}Device GPIO (Raspberry Pi < 5)${NC}"
    group=$(ls -l /dev/gpiomem | awk '{print $4}')
    if [ "$group" = "gpio" ]; then
        echo -e "  ${GREEN}✓${NC} /dev/gpiomem (groupe: gpio)"
    else
        echo -e "  ${RED}✗${NC} /dev/gpiomem (groupe: $group - devrait être gpio)"
        echo -e "  ${YELLOW}→${NC} Corriger : sudo chown root:gpio /dev/gpiomem && sudo chmod 660 /dev/gpiomem"
    fi
fi

# Diagnostic détaillé disponible
echo -e "\n${BLUE}Pour un diagnostic complet :${NC}"
echo -e "  ${GREEN}sudo /opt/tubpi/diagnose_gpio.sh${NC}"
echo ""

# Vérification dépendances Python
echo -e "${BLUE}=== Dépendances Python ===${NC}\n"
echo -e "${YELLOW}Modules Python requis${NC}"
all_deps_ok=true

# Vérifier Flask
if python3 -c "import flask" 2>/dev/null; then
    version=$(python3 -c "import flask; print(flask.__version__)" 2>/dev/null || echo "?")
    echo -e "  ${GREEN}✓${NC} flask ($version)"
else
    echo -e "  ${RED}✗${NC} flask (manquant)"
    all_deps_ok=false
fi

# Vérifier requests
if python3 -c "import requests" 2>/dev/null; then
    version=$(python3 -c "import requests; print(requests.__version__)" 2>/dev/null || echo "?")
    echo -e "  ${GREEN}✓${NC} requests ($version)"
else
    echo -e "  ${RED}✗${NC} requests (manquant)"
    all_deps_ok=false
fi

# Vérifier RPi.GPIO (peut être fourni par rpi-lgpio sur Raspberry Pi 5)
if python3 -c "import RPi.GPIO" 2>/dev/null; then
    # Vérifier si c'est rpi-lgpio (pour Raspberry Pi 5)
    if python3 -c "import RPi.GPIO; print(RPi.GPIO.__file__)" 2>/dev/null | grep -q lgpio; then
        version=$(python3 -c "import lgpio; print(lgpio.__version__)" 2>/dev/null || echo "?")
        echo -e "  ${GREEN}✓${NC} RPi.GPIO via rpi-lgpio ($version) [Raspberry Pi 5]"
    else
        version=$(python3 -c "import RPi.GPIO; print(RPi.GPIO.VERSION)" 2>/dev/null || echo "?")
        echo -e "  ${GREEN}✓${NC} RPi.GPIO ($version)"
    fi
else
    echo -e "  ${RED}✗${NC} RPi.GPIO (manquant)"
    echo -e "  ${YELLOW}→${NC} Pour Raspberry Pi 5 : sudo apt install python3-rpi-lgpio"
    all_deps_ok=false
fi

if ! $all_deps_ok; then
    echo -e "\n  ${YELLOW}→${NC} Installer : sudo apt install python3-flask python3-requests python3-rpi-lgpio"
    echo -e "  ${YELLOW}→${NC} Ou : pip3 install --break-system-packages -r /opt/tubpi/requirements.txt"
fi
echo ""

# Résumé final
echo -e "${BLUE}=== Résumé ===${NC}\n"

if $all_ok && $all_deps_ok; then
    echo -e "${GREEN}✓ Tous les services sont correctement installés${NC}"
else
    echo -e "${YELLOW}⚠ Certains services nécessitent une attention${NC}"
fi

echo -e "\n${YELLOW}Commandes utiles :${NC}"
echo -e "  • Logs en temps réel : ${GREEN}sudo journalctl -u tubpi-onvif-gateway -f${NC}"
echo -e "  • État d'un service  : ${GREEN}sudo systemctl status tubpi-webapp${NC}"
echo -e "  • Redémarrer         : ${GREEN}sudo systemctl restart tubpi-onvif-gateway${NC}"
echo -e "\n${YELLOW}Accès aux interfaces :${NC}"

# Détecter l'IP
if command -v hostname >/dev/null 2>&1; then
    IP=$(hostname -I | awk '{print $1}')
    if [ -n "$IP" ]; then
        echo -e "  • ONVIF Gateway : ${GREEN}http://${IP}:80${NC}"
        echo -e "  • Web App       : ${GREEN}http://${IP}:5000${NC}"
    fi
fi
