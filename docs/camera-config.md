# Configuration Camera

## Fichier de configuration camera.res

Le fichier `/opt/tubpi/camera.res` contient les identifiants pour accéder à la caméra ONVIF.

### Format

```
user=<username>
password=<password>
```

### Création manuelle

```bash
# Créer le fichier
sudo tee /opt/tubpi/camera.res << 'EOF'
user=admin
password=VotreMotDePasse
EOF

# Sécuriser les permissions (lecture par root et groupe dietpi)
sudo chmod 640 /opt/tubpi/camera.res
sudo chown root:dietpi /opt/tubpi/camera.res
```

### Création automatique

Le script `install_services.sh` demande automatiquement les credentials lors de l'installation.

### Vérification

```bash
# Vérifier que le fichier existe
ls -l /opt/tubpi/camera.res

# Devrait afficher: -rw-r----- 1 root dietpi ... /opt/tubpi/camera.res

# Tester le service ONVIF gateway
sudo systemctl restart tubpi-onvif-gateway
sudo journalctl -u tubpi-onvif-gateway -n 20

# Tester la webapp
sudo systemctl restart tubpi-webapp
curl http://localhost:5000/camera/rtsp-url
```

### Sécurité

⚠️ **Important** : 
- Le fichier `camera.res` est exclu de Git via `.gitignore`
- Les permissions sont `640` (lecture/écriture par root, lecture par groupe dietpi)
- Accessible par les services tubpi-onvif-gateway (root) et tubpi-webapp (dietpi)
- Ne jamais commiter ce fichier dans le dépôt

### Modification

Pour changer les credentials :

```bash
# Éditer le fichier
sudo nano /opt/tubpi/camera.res

# Redémarrer le service
sudo systemctl restart tubpi-onvif-gateway
```

### Exemple

Fichier : `/opt/tubpi/camera.res`

```
# Configuration caméra ONVIF
user=admin
password=MonMotDePasseSecurise123
```
