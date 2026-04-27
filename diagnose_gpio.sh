#!/usr/bin/env bash
# Script de diagnostic des permissions GPIO
# Vérifie que l'utilisateur peut accéder aux GPIO pour les services systemd

set -euo pipefail

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Diagnostic des permissions GPIO ===${NC}\n"

# Déterminer l'utilisateur à vérifier
if [ -n "${1:-}" ]; then
    USER_TO_CHECK="$1"
elif [ -n "${SUDO_USER:-}" ]; then
    USER_TO_CHECK="$SUDO_USER"
else
    # Chercher un utilisateur non-root
    for user in pi dietpi debian ubuntu; do
        if id "$user" &>/dev/null; then
            USER_TO_CHECK="$user"
            break
        fi
    done
fi

if [ -z "${USER_TO_CHECK:-}" ]; then
    echo -e "${RED}Impossible de déterminer l'utilisateur à vérifier${NC}"
    echo -e "Usage: $0 [username]"
    exit 1
fi

echo -e "${YELLOW}Vérification pour l'utilisateur : ${USER_TO_CHECK}${NC}\n"

# 1. Vérifier le groupe gpio
echo -e "${BLUE}1. Groupe GPIO${NC}"
if groups "$USER_TO_CHECK" | grep -q gpio; then
    echo -e "  ${GREEN}✓${NC} Utilisateur dans le groupe 'gpio'"
else
    echo -e "  ${RED}✗${NC} Utilisateur PAS dans le groupe 'gpio'"
    echo -e "  ${YELLOW}→${NC} Corriger: sudo usermod -a -G gpio $USER_TO_CHECK"
fi
echo ""

# 2. Vérifier les devices GPIO
echo -e "${BLUE}2. Devices GPIO${NC}"

# Raspberry Pi 5 - gpiochip
if ls /dev/gpiochip* &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Devices gpiochip trouvés (Raspberry Pi 5)"
    for dev in /dev/gpiochip*; do
        perms=$(ls -l "$dev" | awk '{print $1, $3, $4}')
        echo -e "    $dev: $perms"
        
        # Vérifier que le groupe est gpio
        if ls -l "$dev" | awk '{print $4}' | grep -q gpio; then
            echo -e "      ${GREEN}✓${NC} Groupe = gpio"
        else
            echo -e "      ${RED}✗${NC} Groupe != gpio"
            echo -e "      ${YELLOW}→${NC} Corriger: sudo chown root:gpio $dev && sudo chmod 660 $dev"
        fi
    done
else
    echo -e "  ${YELLOW}○${NC} Pas de gpiochip (ancien modèle Pi ?)"
fi
echo ""

# Anciens modèles - gpiomem
if [ -e /dev/gpiomem ]; then
    echo -e "  ${GREEN}✓${NC} Device gpiomem trouvé (Raspberry Pi < 5)"
    perms=$(ls -l /dev/gpiomem | awk '{print $1, $3, $4}')
    echo -e "    /dev/gpiomem: $perms"
    
    if ls -l /dev/gpiomem | awk '{print $4}' | grep -q gpio; then
        echo -e "      ${GREEN}✓${NC} Groupe = gpio"
    else
        echo -e "      ${RED}✗${NC} Groupe != gpio"
        echo -e "      ${YELLOW}→${NC} Corriger: sudo chown root:gpio /dev/gpiomem && sudo chmod 660 /dev/gpiomem"
    fi
else
    echo -e "  ${YELLOW}○${NC} Pas de gpiomem"
fi
echo ""

# 3. Test d'accès Python
echo -e "${BLUE}3. Test d'accès Python${NC}"

# Test avec rpi-lgpio
if python3 -c "import RPi.GPIO" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Module RPi.GPIO importable"
    
    # Test en tant qu'utilisateur cible
    if sudo -u "$USER_TO_CHECK" python3 << 'EOF' 2>/dev/null
import RPi.GPIO as GPIO
try:
    GPIO.setmode(GPIO.BCM)
    print("OK")
    GPIO.cleanup()
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
EOF
    then
        echo -e "  ${GREEN}✓${NC} Test GPIO réussi pour l'utilisateur $USER_TO_CHECK"
    else
        echo -e "  ${RED}✗${NC} Test GPIO échoué pour l'utilisateur $USER_TO_CHECK"
        echo -e "  ${YELLOW}→${NC} L'utilisateur ne peut pas accéder aux GPIO"
    fi
else
    echo -e "  ${RED}✗${NC} Module RPi.GPIO non disponible"
    echo -e "  ${YELLOW}→${NC} Installer: sudo apt install python3-rpi-lgpio"
fi
echo ""

# 4. Règles udev
echo -e "${BLUE}4. Règles udev${NC}"
if [ -f /etc/udev/rules.d/99-gpio.rules ]; then
    echo -e "  ${GREEN}✓${NC} Règle udev GPIO présente"
    echo -e "    Contenu:"
    cat /etc/udev/rules.d/99-gpio.rules | grep -v '^#' | grep -v '^$' | sed 's/^/    /'
else
    echo -e "  ${YELLOW}○${NC} Pas de règle udev GPIO personnalisée"
    echo -e "  ${YELLOW}→${NC} Installer: sudo cp systemd/99-gpio.rules /etc/udev/rules.d/"
    echo -e "  ${YELLOW}→${NC} Puis: sudo udevadm control --reload-rules && sudo udevadm trigger"
fi
echo ""

# 5. Services systemd
echo -e "${BLUE}5. Services systemd${NC}"
if [ -f /etc/systemd/system/tubpi-webapp.service ]; then
    echo -e "  ${GREEN}✓${NC} Service tubpi-webapp présent"
    
    # Vérifier les DeviceAllow
    if grep -q "DeviceAllow" /etc/systemd/system/tubpi-webapp.service; then
        echo -e "  ${GREEN}✓${NC} DeviceAllow configuré"
    else
        echo -e "  ${YELLOW}○${NC} Pas de DeviceAllow (peut bloquer l'accès GPIO)"
        echo -e "  ${YELLOW}→${NC} Mettre à jour le service pour ajouter DeviceAllow"
    fi
    
    # Vérifier PrivateTmp
    if grep -q "PrivateTmp=true" /etc/systemd/system/tubpi-webapp.service; then
        echo -e "  ${YELLOW}⚠${NC}  PrivateTmp=true peut bloquer l'accès aux devices"
    fi
else
    echo -e "  ${YELLOW}○${NC} Service tubpi-webapp non installé"
fi
echo ""

# 6. Modèle de Raspberry Pi
echo -e "${BLUE}6. Modèle Raspberry Pi${NC}"
if [ -f /proc/device-tree/model ]; then
    model=$(cat /proc/device-tree/model | tr -d '\0')
    echo -e "  ${GREEN}✓${NC} Modèle: $model"
    
    if echo "$model" | grep -q "Raspberry Pi 5"; then
        echo -e "  ${BLUE}ℹ${NC}  Pi 5 détecté - utilise /dev/gpiochip*"
        echo -e "  ${BLUE}ℹ${NC}  Bibliothèque recommandée: rpi-lgpio ou pigpio"
    else
        echo -e "  ${BLUE}ℹ${NC}  Pi < 5 - utilise /dev/gpiomem"
        echo -e "  ${BLUE}ℹ${NC}  Bibliothèques compatibles: RPi.GPIO, rpi-lgpio, pigpio"
    fi
else
    echo -e "  ${YELLOW}○${NC} Impossible de déterminer le modèle"
fi
echo ""

# Résumé
echo -e "${BLUE}=== Résumé ===${NC}\n"

all_ok=true

# Vérifier tous les critères
if ! groups "$USER_TO_CHECK" | grep -q gpio; then
    all_ok=false
fi

if ls /dev/gpiochip* &>/dev/null; then
    for dev in /dev/gpiochip*; do
        if ! ls -l "$dev" | awk '{print $4}' | grep -q gpio; then
            all_ok=false
        fi
    done
fi

if [ -e /dev/gpiomem ]; then
    if ! ls -l /dev/gpiomem | awk '{print $4}' | grep -q gpio; then
        all_ok=false
    fi
fi

if $all_ok; then
    echo -e "${GREEN}✓ Toutes les vérifications sont OK${NC}"
    echo -e "${GREEN}L'utilisateur $USER_TO_CHECK devrait pouvoir accéder aux GPIO${NC}"
    echo -e "\n${YELLOW}Note:${NC} Si vous venez d'ajouter l'utilisateur au groupe gpio,"
    echo -e "déconnectez-vous et reconnectez-vous (ou redémarrez) pour appliquer les changements."
else
    echo -e "${YELLOW}⚠ Certains problèmes ont été détectés${NC}"
    echo -e "\n${YELLOW}Actions recommandées:${NC}"
    echo -e "1. Ajouter l'utilisateur au groupe: ${GREEN}sudo usermod -a -G gpio $USER_TO_CHECK${NC}"
    echo -e "2. Corriger les permissions: ${GREEN}sudo chown root:gpio /dev/gpiochip* /dev/gpiomem 2>/dev/null; sudo chmod 660 /dev/gpiochip* /dev/gpiomem 2>/dev/null${NC}"
    echo -e "3. Installer la règle udev: ${GREEN}sudo cp systemd/99-gpio.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger${NC}"
    echo -e "4. Redémarrer les services: ${GREEN}sudo systemctl daemon-reload && sudo systemctl restart tubpi-webapp${NC}"
    echo -e "5. Déconnexion/reconnexion ou redémarrage"
fi
