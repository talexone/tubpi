# Services systemd Tubpi

Ce dossier contient les fichiers de service systemd pour automatiser le démarrage de Tubpi.

## Fichiers

- **tubpi-network-setup.service** : Configure le réseau au démarrage (eth0/eth1, NAT)
- **tubpi-onvif-gateway.service** : Lance le proxy ONVIF sur le port 80
- **tubpi-webapp.service** : Lance l'interface web sur le port 5000

## Installation

**Ne copiez PAS ces fichiers manuellement.** Utilisez le script d'installation fourni :

```bash
sudo /opt/tubpi/install_services.sh
```

## Emplacement

Ces fichiers seront copiés dans `/etc/systemd/system/` lors de l'installation.

## Documentation

Voir [../docs/services.md](../docs/services.md) pour la documentation complète.
