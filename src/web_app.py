"""Application web minimale pour contrôler le rail de caméra."""

from flask import Flask, jsonify, request, render_template
from motor_driver import MotorDriver

app = Flask(__name__)

try:
    motor = MotorDriver(forward_pin=20, backward_pin=21, enable_pin=None)
    if not motor.enabled:
        motor = None
except Exception:
    motor = None

@app.route('/')
def index():
    return render_template('test.html')

@app.before_request
def check_motor_available():
    if request.endpoint == 'move' and motor is None:
        return jsonify({'error': 'GPIO non disponible ou pas exécuté sur Raspberry Pi'}), 503

@app.route('/move', methods=['POST'])
def move():
    data = request.json or {}
    direction = data.get('direction')
    speed = data.get('speed', 50)

    if direction not in ('forward', 'backward', 'stop', 'calibrate'):
        return jsonify({'error': 'direction invalide'}), 400

    try:
        if direction == 'forward':
            motor.move_forward(speed)
        elif direction == 'backward':
            motor.move_backward(speed)
        elif direction == 'stop':
            motor.stop()
        elif direction == 'calibrate':
            result = motor.calibrate()
            return jsonify({'direction': direction, 'result': result})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

    return jsonify({'direction': direction, 'speed': speed})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    motor.cleanup()
    return jsonify({'message': 'GPIO nettoyés, moteur arrêté'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
