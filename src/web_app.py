"""Application web minimale pour contrôler le rail de caméra."""

import requests
from flask import Flask, jsonify, request, render_template
from motor_driver import MotorDriver
from camera_onvif import CameraOnvif

app = Flask(__name__)

motor = None
camera = None

def init_motor():
    global motor, camera
    if motor is None:
        try:
            motor = MotorDriver()
            if motor.is_available():
                print('GPIO disponible : initialisation réussie.')
            else:
                print('GPIO non disponible : vérifiez que le programme est exécuté sur un Raspberry Pi avec accès aux GPIO.')
                motor = None
        except Exception as exc:
            # Si GPIO busy, c'est probablement onvif-gateway qui gère le moteur
            if 'GPIO busy' in str(exc):
                print(f'GPIO déjà utilisé par un autre service (probablement onvif-gateway): {exc}')
                print('Le contrôle moteur se fait via le service onvif-gateway.')
            else:
                print(f'GPIO non disponible: {exc}')
            motor = None

    if camera is None:
        camera = CameraOnvif(host='192.168.1.108', motor=motor)
    return motor

@app.route('/')
def index():
    return render_template('test.html')

@app.route('/move', methods=['POST'])
def move():
    print('move')
    data = request.json or {}
    direction = data.get('direction')

    if direction not in ('forward', 'backward', 'stop', 'calibrate', 'focus_plus', 'focus_minus'):
        return jsonify({'error': 'direction invalide'}), 400

    # Initialiser le moteur si pas déjà fait
    if motor is None:
        init_motor()
    
    # Si motor est None (géré par onvif-gateway), déléguer à l'API
    if motor is None:
        # Pour les commandes focus, ne pas déléguer (elles passent par ONVIF)
        if direction in ('focus_plus', 'focus_minus'):
            return jsonify({
                'error': 'Commandes focus disponibles uniquement via ONVIF',
                'hint': 'Utilisez un client ONVIF pour contrôler le focus'
            }), 503
        
        # Déléguer les commandes moteur à onvif-gateway
        if direction in ('forward', 'backward', 'stop', 'calibrate'):
            try:
                response = requests.post(
                    'http://localhost/api/motor/move',
                    json={'direction': direction},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    data['source'] = 'onvif-gateway'
                    return jsonify(data)
                else:
                    return jsonify({
                        'error': f'Erreur API onvif-gateway: {response.status_code}',
                        'details': response.text
                    }), response.status_code
            except Exception as exc:
                return jsonify({
                    'error': f'Impossible de contacter onvif-gateway: {exc}'
                }), 503

    # Si motor est disponible localement, l'utiliser directement
    try:
        if direction == 'forward':
            motor.move_forward()
        elif direction == 'backward':
            motor.move_backward()
        elif direction == 'stop':
            motor.stop()
        elif direction == 'calibrate':
            result = motor.calibrate()
            return jsonify({'direction': direction, 'result': result, 'source': 'local'})
        elif direction == 'focus_plus':
            result = camera.focus_plus()
            result['source'] = 'local'
            return jsonify(result)
        elif direction == 'focus_minus':
            result = camera.focus_minus()
            result['source'] = 'local'
            return jsonify(result)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

    return jsonify({'direction': direction, 'source': 'local'})

@app.route('/status', methods=['GET'])
def status():
    """Retourne l'état actuel du système.
    
    Si le moteur n'est pas disponible localement (géré par onvif-gateway),
    récupère les informations depuis l'API du service onvif-gateway.
    """
    if motor is None:
        init_motor()
    
    # Si motor est None, on essaie de récupérer les infos depuis onvif-gateway
    if motor is None:
        try:
            # onvif-gateway tourne sur port 80 en local
            response = requests.get('http://localhost/api/motor/status', timeout=2)
            if response.status_code == 200:
                data = response.json()
                data['source'] = 'onvif-gateway'
                return jsonify(data)
            else:
                return jsonify({
                    'available': False,
                    'message': 'Contrôle moteur géré par le service onvif-gateway (port 80)',
                    'hint': 'Les commandes moteur se font via ONVIF ou le service onvif-gateway',
                    'error': f'Erreur API onvif-gateway: {response.status_code}'
                }), 200
        except Exception as exc:
            return jsonify({
                'available': False,
                'message': 'Contrôle moteur géré par le service onvif-gateway (port 80)',
                'hint': 'Les commandes moteur se font via ONVIF ou le service onvif-gateway',
                'error': f'Impossible de contacter onvif-gateway: {exc}'
            }), 200
    
    # Si motor est disponible localement, on l'utilise directement
    try:
        limit_status = motor.get_limit_switches_status()
        encoder_stats = motor.get_encoder_stats()
        return jsonify({
            'available': True,
            'source': 'local',
            'limit_switches': limit_status,
            'can_move_forward': motor.can_move_forward(),
            'can_move_backward': motor.can_move_backward(),
            'encoder': encoder_stats
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/encoder', methods=['GET'])
def encoder_info():
    """Retourne les informations détaillées de l'encodeur.
    
    Si le moteur n'est pas disponible localement, récupère depuis onvif-gateway.
    """
    if motor is None:
        init_motor()
    
    # Si motor est None, récupérer depuis onvif-gateway
    if motor is None:
        try:
            response = requests.get('http://localhost/api/motor/encoder', timeout=2)
            if response.status_code == 200:
                data = response.json()
                data['source'] = 'onvif-gateway'
                return jsonify(data)
            else:
                return jsonify({
                    'available': False,
                    'message': 'Encodeur géré par le service onvif-gateway',
                    'error': f'Erreur API: {response.status_code}'
                }), 503
        except Exception as exc:
            return jsonify({
                'available': False,
                'message': 'Encodeur non disponible',
                'error': str(exc)
            }), 503
    
    # Sinon utiliser motor local
    try:
        stats = motor.get_encoder_stats()
        stats['source'] = 'local'
        return jsonify(stats)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/encoder/reset', methods=['POST'])
def encoder_reset():
    """Réinitialise la position de l'encodeur."""
    if motor is None:
        init_motor()
    
    if motor is None:
        return jsonify({'error': 'GPIO non disponible'}), 503
    
    try:
        motor.reset_encoder_position()
        return jsonify({
            'success': True,
            'message': 'Position réinitialisée',
            'position': motor.get_encoder_position()
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/limit_switches', methods=['POST'])
def set_limit_switches():
    """Active ou désactive les capteurs de fin de course."""
    if motor is None:
        init_motor()
    
    # Si motor est None, déléguer à onvif-gateway
    if motor is None:
        try:
            data = request.get_json()
            response = requests.post('http://localhost/api/motor/limit_switches', 
                                    json=data, 
                                    timeout=2)
            if response.status_code == 200:
                result = response.json()
                result['source'] = 'onvif-gateway'
                return jsonify(result)
            else:
                return jsonify({
                    'error': f'Erreur API onvif-gateway: {response.status_code}'
                }), response.status_code
        except Exception as exc:
            return jsonify({
                'error': 'Impossible de contacter onvif-gateway',
                'details': str(exc)
            }), 503
    
    # Sinon utiliser motor local
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        
        motor.set_limit_switches_enabled(enabled)
        
        return jsonify({
            'success': True,
            'enabled': motor.get_limit_switches_enabled(),
            'message': f"Capteurs de fin de course {'activés' if enabled else 'désactivés'}",
            'source': 'local'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/encoder', methods=['POST'])
def set_encoder():
    """Active ou désactive l'encodeur de position."""
    if motor is None:
        init_motor()
    
    # Si motor est None, déléguer à onvif-gateway
    if motor is None:
        try:
            data = request.get_json()
            response = requests.post('http://localhost/api/motor/encoder', 
                                    json=data, 
                                    timeout=2)
            if response.status_code == 200:
                result = response.json()
                result['source'] = 'onvif-gateway'
                return jsonify(result)
            else:
                return jsonify({
                    'error': f'Erreur API onvif-gateway: {response.status_code}'
                }), response.status_code
        except Exception as exc:
            return jsonify({
                'error': 'Impossible de contacter onvif-gateway',
                'details': str(exc)
            }), 503
    
    # Sinon utiliser motor local
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        
        motor.set_encoder_enabled(enabled)
        
        return jsonify({
            'success': True,
            'enabled': motor.get_encoder_enabled(),
            'message': f"Encodeur {'activé' if enabled else 'désactivé'}",
            'source': 'local'
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    if motor is None:
        return jsonify({'message': 'Aucun GPIO à nettoyer'}), 200
    motor.cleanup()
    return jsonify({'message': 'GPIO nettoyés, moteur arrêté'})

@app.route('/camera/rtsp-url', methods=['GET'])
def get_rtsp_url():
    """Retourne l'URL RTSP complète avec credentials."""
    try:
        # Lire les credentials depuis camera.res
        with open('/opt/tubpi/camera.res', 'r') as f:
            creds = {}
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    creds[key.strip()] = value.strip()
            username = creds.get('user', 'admin')
            password = creds.get('password', '')
    except Exception as exc:
        return jsonify({
            'error': 'Impossible de lire les credentials',
            'details': str(exc)
        }), 500
    
    # Configuration caméra
    camera_ip = '192.168.1.108'
    camera_port = 554
    camera_path = '/cam/realmonitor?channel=1&subtype=1'
    
    # Construire l'URL RTSP avec authentification
    rtsp_url = f'rtsp://{username}:{password}@{camera_ip}:{camera_port}{camera_path}'
    rtsp_url_display = f'rtsp://{username}:****@{camera_ip}:{camera_port}{camera_path}'
    
    return jsonify({
        'url': rtsp_url,
        'display_url': rtsp_url_display,
        'vlc_url': f'vlc://{rtsp_url}'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
