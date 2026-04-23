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

# Vérifier les dépendances Python
echo -e "${GREEN}Vérification des dépendances Python...${NC}"
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip3 install -r "$PROJECT_DIR/requirements.txt" 2>&1 | grep -v "Requirement already satisfied" || true
else
    echo -e "${YELLOW}Attention : requirements.txt non trouvé${NC}"
fi

# Vérifier les permissions GPIO pour l'utilisateur pi
echo -e "${GREEN}Configuration des permissions GPIO...${NC}"
if ! groups pi | grep -q gpio; then
    usermod -a -G gpio pi
    echo -e "${GREEN}✓ Utilisateur 'pi' ajouté au groupe 'gpio'${NC}"
else
    echo -e "${GREEN}✓ Utilisateur 'pi' déjà dans le groupe 'gpio'${NC}"
fi

# Copier les fichiers de service
echo -e "\n${GREEN}Installation des fichiers de service systemd...${NC}"

services=(
    "tubpi-network-setup"
    "tubpi-onvif-gateway"
    "tubpi-webapp"
)

for service in "${services[@]}"; do
    if [ -f "$PROJECT_DIR/systemd/${service}.service" ]; then
        echo -e "  ${GREEN}→${NC} Installation de ${service}.service"
        cp "$PROJECT_DIR/systemd/${service}.service" "$SYSTEMD_DIR/"
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
