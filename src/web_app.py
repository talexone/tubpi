"""Application web minimale pour contrôler le rail de caméra."""

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

@app.before_request
def check_motor_available():
    if request.endpoint == 'move':
        init_motor()
        print(f'check_motor_available: endpoint={request.endpoint}, motor={"available" if motor else "unavailable"}')
        if motor is None:
            return jsonify({'error': 'GPIO non disponible ou pas exécuté sur Raspberry Pi'}), 503

@app.route('/move', methods=['POST'])
def move():
    print('move')
    data = request.json or {}
    direction = data.get('direction')

    if direction not in ('forward', 'backward', 'stop', 'calibrate', 'focus_plus', 'focus_minus'):
        return jsonify({'error': 'direction invalide'}), 400

    if motor is None:
        return jsonify({'error': 'GPIO non disponible ou pas exécuté sur Raspberry Pi'}), 503

    try:
        if direction == 'forward':
            motor.move_forward()
        elif direction == 'backward':
            motor.move_backward()
        elif direction == 'stop':
            motor.stop()
        elif direction == 'calibrate':
            result = motor.calibrate()
            return jsonify({'direction': direction, 'result': result})
        elif direction == 'focus_plus':
            result = camera.focus_plus()
            return jsonify(result)
        elif direction == 'focus_minus':
            result = camera.focus_minus()
            return jsonify(result)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

    return jsonify({'direction': direction})

@app.route('/status', methods=['GET'])
def status():
    """Retourne l'état actuel du système."""
    if motor is None:
        init_motor()
    
    if motor is None:
        return jsonify({
            'available': False,
            'message': 'Contrôle moteur géré par le service onvif-gateway (port 80)',
            'hint': 'Les commandes moteur se font via ONVIF ou le service onvif-gateway'
        }), 200
    
    try:
        limit_status = motor.get_limit_switches_status()
        encoder_stats = motor.get_encoder_stats()
        return jsonify({
            'available': True,
            'limit_switches': limit_status,
            'can_move_forward': motor.can_move_forward(),
            'can_move_backward': motor.can_move_backward(),
            'encoder': encoder_stats
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/encoder', methods=['GET'])
def encoder_info():
    """Retourne les informations détaillées de l'encodeur."""
    if motor is None:
        init_motor()
    
    if motor is None:
        return jsonify({
            'available': False,
            'message': 'GPIO non disponible'
        }), 503
    
    try:
        return jsonify(motor.get_encoder_stats())
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

@app.route('/shutdown', methods=['POST'])
def shutdown():
    if motor is None:
        return jsonify({'message': 'Aucun GPIO à nettoyer'}), 200
    motor.cleanup()
    return jsonify({'message': 'GPIO nettoyés, moteur arrêté'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
