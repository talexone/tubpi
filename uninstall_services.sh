#!/usr/bin/env bash
# Script de désinstallation des services systemd Tubpi

set -euo pipefail

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Ce script doit être exécuté avec sudo ou en root.${NC}" >&2
  exit 1
fi

echo -e "${YELLOW}=== Désinstallation des services Tubpi ===${NC}\n"

SYSTEMD_DIR="/etc/systemd/system"

services=(
    "tubpi-network-setup"
    "tubpi-onvif-gateway"
    "tubpi-webapp"
)

for service in "${services[@]}"; do
    if systemctl is-active --quiet "${service}.service"; then
        echo -e "${YELLOW}→ Arrêt de ${service}...${NC}"
        systemctl stop "${service}.service"
    fi
    
    if systemctl is-enabled --quiet "${service}.service" 2>/dev/null; then
        echo -e "${YELLOW}→ Désactivation de ${service}...${NC}"
        systemctl disable "${service}.service"
    fi
    
    if [ -f "$SYSTEMD_DIR/${service}.service" ]; then
        echo -e "${GREEN}→ Suppression de ${service}.service${NC}"
        rm -f "$SYSTEMD_DIR/${service}.service"
    fi
done

echo -e "\n${GREEN}Rechargement de systemd...${NC}"
systemctl daemon-reload

echo -e "\n${GREEN}✓ Désinstallation terminée${NC}"
echo -e "${YELLOW}Note : Les fichiers du projet dans /opt/tubpi n'ont pas été supprimés.${NC}"
