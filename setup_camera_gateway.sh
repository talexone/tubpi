#!/usr/bin/env bash
# Configure le Raspberry Pi comme passerelle HTTP/ONVIF/RTSP vers la caméra
# connectée sur eth1 (192.168.1.108). Le réseau local reste sur eth0.

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Ce script doit être exécuté avec sudo ou en root." >&2
  exit 1
fi

ETH0_ADDR=192.168.11.28
CAMERA_ADDR=192.168.1.108

cat <<'EOF'
Configuration de la passerelle caméra :
- RPi eth0 = 192.168.11.28
- RPi eth1 = 192.168.1.30
- Caméra = 192.168.1.108

L'objectif : accéder à la caméra depuis le réseau 192.168.11.0/24 via 192.168.11.28.
EOF

echo "Activation du routage IP..."
sysctl -w net.ipv4.ip_forward=1 > /dev/null
if [ ! -f /etc/sysctl.d/99-ipforward.conf ]; then
  cat > /etc/sysctl.d/99-ipforward.conf <<EOF
net.ipv4.ip_forward=1
EOF
fi

# Vidage des règles existantes de forwarding si elles existent déjà
iptables -D FORWARD -i eth0 -o eth1 -s 192.168.11.0/24 -d 192.168.1.0/24 -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i eth1 -o eth0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
iptables -t nat -D PREROUTING -d ${ETH0_ADDR} -p tcp --dport 80 -j DNAT --to-destination ${CAMERA_ADDR}:80 2>/dev/null || true
iptables -t nat -D PREROUTING -d ${ETH0_ADDR} -p tcp --dport 443 -j DNAT --to-destination ${CAMERA_ADDR}:443 2>/dev/null || true
iptables -t nat -D PREROUTING -d ${ETH0_ADDR} -p tcp --dport 554 -j DNAT --to-destination ${CAMERA_ADDR}:554 2>/dev/null || true
iptables -t nat -D PREROUTING -d ${ETH0_ADDR} -p udp --dport 554 -j DNAT --to-destination ${CAMERA_ADDR}:554 2>/dev/null || true
iptables -t nat -D POSTROUTING -s 192.168.11.0/24 -d 192.168.1.0/24 -j MASQUERADE 2>/dev/null || true

echo "Ajout des règles de routage NAT..."
iptables -A FORWARD -i eth0 -o eth1 -s 192.168.11.0/24 -d 192.168.1.0/24 -j ACCEPT
iptables -A FORWARD -i eth1 -o eth0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -t nat -A PREROUTING -d ${ETH0_ADDR} -p tcp --dport 80 -j DNAT --to-destination ${CAMERA_ADDR}:80
iptables -t nat -A PREROUTING -d ${ETH0_ADDR} -p tcp --dport 443 -j DNAT --to-destination ${CAMERA_ADDR}:443
iptables -t nat -A PREROUTING -d ${ETH0_ADDR} -p tcp --dport 554 -j DNAT --to-destination ${CAMERA_ADDR}:554
iptables -t nat -A PREROUTING -d ${ETH0_ADDR} -p udp --dport 554 -j DNAT --to-destination ${CAMERA_ADDR}:554
iptables -t nat -A POSTROUTING -s 192.168.11.0/24 -d 192.168.1.0/24 -j MASQUERADE

cat <<EOF
Passerelle configurée.

Accès de la caméra via le RPi :
- HTTP/ONVIF : http://${ETH0_ADDR}/
- RTSP : rtsp://${ETH0_ADDR}:554/

Si votre caméra utilise d'autres ports, ajoutez-les en adaptant ce script.
EOF
