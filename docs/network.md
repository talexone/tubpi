# Passerelle caméra

Ce document décrit la configuration pour accéder à la caméra IP connectée sur `eth1` depuis le réseau local sur `eth0`.

## Topologie

- Raspberry Pi `eth0` : `192.168.11.28` (réseau local)
- Raspberry Pi `eth1` : `192.168.1.30` (réseau caméra)
- Caméra IP PTZ : `192.168.1.108`

## Objectif

Permettre l'accès à la caméra depuis le réseau local en utilisant l'adresse du Raspberry Pi `192.168.11.28`.

## Solution

1. Activer le routage IPv4 sur le Raspberry Pi.
2. Ajouter des règles `iptables` pour autoriser le forwarding entre `eth0` et `eth1`.
3. Ajouter des règles NAT/DNAT pour rediriger le trafic HTTP/ONVIF/RTSP reçu sur `192.168.11.28` vers `192.168.1.108`.

## Commande d'installation

Utiliser le script `setup_camera_gateway.sh` :

```bash
sudo bash setup_camera_gateway.sh
```

## Accès depuis le réseau local

- HTTP/ONVIF (port 80/443) : `http://192.168.11.28/`
- RTSP (port 554) : `rtsp://192.168.11.28:554/`

Si la caméra utilise un port différent, adapter le script `setup_camera_gateway.sh`.
