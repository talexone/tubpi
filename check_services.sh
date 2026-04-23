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
echo -e "${YELLOW}Permissions GPIO${NC}"
if groups pi | grep -q gpio; then
    echo -e "  ${GREEN}✓${NC} Utilisateur 'pi' dans le groupe 'gpio'"
else
    echo -e "  ${RED}✗${NC} Utilisateur 'pi' PAS dans le groupe 'gpio'"
    echo -e "  ${YELLOW}→${NC} Exécuter : sudo usermod -a -G gpio pi"
fi
echo ""

# Vérification dépendances Python
echo -e "${BLUE}=== Dépendances Python ===${NC}\n"
required_packages=("flask" "requests" "RPi.GPIO")
echo -e "${YELLOW}Modules Python requis${NC}"
all_deps_ok=true
for pkg in "${required_packages[@]}"; do
    if pip3 show "$pkg" >/dev/null 2>&1; then
        version=$(pip3 show "$pkg" | grep Version | awk '{print $2}')
        echo -e "  ${GREEN}✓${NC} $pkg ($version)"
    else
        echo -e "  ${RED}✗${NC} $pkg (manquant)"
        all_deps_ok=false
    fi
done

if ! $all_deps_ok; then
    echo -e "\n  ${YELLOW}→${NC} Installer : pip3 install -r /opt/tubpi/requirements.txt"
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
