#!/usr/bin/env python3
"""Proxy HTTP simple pour relayer les requêtes ONVIF du réseau local vers la caméra et intercepter focus+ / focus-."""

import argparse
import hashlib
import http.server
import json
import logging
import os
import re
import socket
import socketserver
import struct
import threading
import urllib.parse
import uuid
import xml.etree.ElementTree as ET

import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

from motor_driver import MotorDriver

# Configuration de la caméra
CAMERA_HOST = '192.168.1.108'
CAMERA_PORT = 80
CAMERA_URL = f'http://{CAMERA_HOST}:{CAMERA_PORT}'

def load_camera_credentials(config_file='/opt/tubpi/camera.res'):
    """Charge les credentials depuis le fichier de configuration.
    
    Format attendu:
        user=<username>
        password=<password>
    
    Returns:
        tuple: (username, password)
    """
    try:
        credentials = {}
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
        
        username = credentials.get('user', 'admin')
        password = credentials.get('password', '')
        
        if not password:
            logging.warning(f"Mot de passe vide dans {config_file}")
        
        return username, password
    except FileNotFoundError:
        logging.error(f"Fichier de configuration {config_file} introuvable")
        logging.error(f"Créez le fichier avec: user=<username>\\npassword=<password>")
        raise
    except Exception as e:
        logging.error(f"Erreur lors de la lecture de {config_file}: {e}")
        raise

# Charger les credentials depuis le fichier
CAMERA_USER, CAMERA_PASSWORD = load_camera_credentials()

MOTOR_FORWARD_PIN = 20
MOTOR_BACKWARD_PIN = 21
LISTEN_PORT = 80

WS_DISCOVERY_MCAST_ADDR = '239.255.255.250'
WS_DISCOVERY_MCAST_PORT = 3702
_DEVICE_UUID = str(uuid.uuid4())  # stable for the lifetime of the process

debug_mode = False
test_mode = False

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logging.info(f'Connexion à la caméra: {CAMERA_USER}@{CAMERA_HOST}:{CAMERA_PORT}')

_proxy_auth = HTTPDigestAuth(CAMERA_USER, CAMERA_PASSWORD)

motor = MotorDriver(forward_pin=MOTOR_FORWARD_PIN, backward_pin=MOTOR_BACKWARD_PIN)
if motor.is_available():
    logging.info('Motor driver initialisé')
else:
    logging.warning('Motor driver non disponible : le proxy continuera à relayer les requêtes sans piloter le moteur')


# ---------------------------------------------------------------------------
# WS-Discovery helpers
# ---------------------------------------------------------------------------

def _get_local_ip_toward(target_ip):
    """Return the local IP on the interface used to reach *target_ip*."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((target_ip, 80))
            return s.getsockname()[0]
    except Exception:
        return '0.0.0.0'


def _is_probe_message(data):
    """Return True if *data* is a WS-Discovery Probe SOAP message."""
    try:
        root = ET.fromstring(data)
        for elem in root.iter():
            local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if local == 'Probe':
                return True
    except ET.ParseError:
        pass
    return False


def _parse_message_id(data):
    """Extract wsa:MessageID from a WS-Discovery Probe."""
    try:
        root = ET.fromstring(data)
        for ns_uri in (
            'http://schemas.xmlsoap.org/ws/2004/08/addressing',
            'http://www.w3.org/2005/08/addressing',
        ):
            elem = root.find(f'.//{{{ns_uri}}}MessageID')
            if elem is not None and elem.text:
                return elem.text
    except ET.ParseError:
        pass
    return f'urn:uuid:{uuid.uuid4()}'


def _build_probe_match(relates_to, local_ip, http_port):
    """Build a WS-Discovery ProbeMatches response."""
    msg_id = f'urn:uuid:{uuid.uuid4()}'
    endpoint = f'urn:uuid:{_DEVICE_UUID}'
    xaddr = f'http://{local_ip}:{http_port}/onvif/device_service'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope'
        ' xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
        ' xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"'
        ' xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"'
        ' xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
        '<s:Header>'
        f'<a:MessageID>{msg_id}</a:MessageID>'
        f'<a:RelatesTo>{relates_to}</a:RelatesTo>'
        '<a:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:To>'
        '<a:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches</a:Action>'
        '</s:Header>'
        '<s:Body>'
        '<d:ProbeMatches>'
        '<d:ProbeMatch>'
        f'<a:EndpointReference><a:Address>{endpoint}</a:Address></a:EndpointReference>'
        '<d:Types>dn:NetworkVideoTransmitter</d:Types>'
        '<d:Scopes>'
        'onvif://www.onvif.org/type/video_encoder '
        'onvif://www.onvif.org/Profile/Streaming'
        '</d:Scopes>'
        f'<d:XAddrs>{xaddr}</d:XAddrs>'
        '<d:MetadataVersion>1</d:MetadataVersion>'
        '</d:ProbeMatch>'
        '</d:ProbeMatches>'
        '</s:Body>'
        '</s:Envelope>'
    ).encode('utf-8')


def run_ws_discovery(http_port):
    """Listen on the WS-Discovery multicast group and reply to Probe messages."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass
    sock.bind(('', WS_DISCOVERY_MCAST_PORT))
    mreq = struct.pack('4sL', socket.inet_aton(WS_DISCOVERY_MCAST_ADDR), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    logging.info(
        'WS-Discovery listener actif sur %s:%s',
        WS_DISCOVERY_MCAST_ADDR, WS_DISCOVERY_MCAST_PORT,
    )

    while True:
        try:
            data, addr = sock.recvfrom(65535)
            logging.debug('WS-Discovery reçu de %s : %s', addr, data[:200])
            if _is_probe_message(data):
                msg_id = _parse_message_id(data)
                local_ip = _get_local_ip_toward(addr[0])
                response = _build_probe_match(msg_id, local_ip, http_port)
                sock.sendto(response, addr)
                logging.info('WS-Discovery ProbeMatch envoyé à %s (XAddrs -> %s:%s)', addr, local_ip, http_port)
        except Exception as exc:
            logging.error('WS-Discovery erreur: %s', exc)


# ---------------------------------------------------------------------------
# Response body IP rewriting
# ---------------------------------------------------------------------------

_TEXT_CONTENT_TYPES = ('xml', 'soap', 'text', 'json')


def _rewrite_body_ips(content, content_type, client_ip):
    """Replace camera host:port references in text/XML response bodies.

    ONVIF SOAP responses embed the camera's IP in capability URLs and stream
    URIs (e.g. rtsp://192.168.1.108/...).  The ONVIF client must reach those
    addresses through the proxy, so we rewrite them to the proxy IP that is
    visible from the client's network.
    """
    ct = (content_type or '').lower()
    if not any(t in ct for t in _TEXT_CONTENT_TYPES):
        return content
    try:
        text = content.decode('utf-8')
    except (UnicodeDecodeError, AttributeError):
        return content
    proxy_ip = _get_local_ip_toward(client_ip)
    camera_with_port = f'{CAMERA_HOST}:{CAMERA_PORT}'
    proxy_with_port = f'{proxy_ip}:{LISTEN_PORT}'
    text = text.replace(camera_with_port, proxy_with_port)
    text = text.replace(CAMERA_HOST, proxy_ip)
    return text.encode('utf-8')


def _xml_contains_focus_command(body_bytes):
    try:
        root = ET.fromstring(body_bytes)
    except ET.ParseError:
        return None

    for elem in root.iter():
        tag = elem.tag
        if tag.endswith('FocusMove') or tag.endswith('Focus'):
            return elem
    return None


def _get_soap_action(body_bytes):
    """Extract the SOAP action/method name from the request body."""
    try:
        root = ET.fromstring(body_bytes)
        for elem in root.iter():
            local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            # Common ONVIF operations
            if local in ('GetImagingSettings', 'SetImagingSettings', 'GetOptions',
                        'GetStatus', 'GetMoveOptions', 'Move', 'Stop',
                        'ContinuousMove', 'RelativeMove', 'AbsoluteMove',
                        'GetPresets', 'SetPreset', 'GotoPreset'):
                return local
    except ET.ParseError:
        pass
    return None


def _get_focus_direction(body_bytes):
    try:
        root = ET.fromstring(body_bytes)
    except ET.ParseError:
        return None

    in_focus_context = False
    for elem in root.iter():
        local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        # Explicit stop commands
        if local in ('Stop', 'StopFocus', 'MoveStop'):
            return 'stop'
        if local in ('FocusMove', 'ContinuousFocus', 'Focus', 'Continuous', 'Relative', 'Absolute', 'Move'):
            in_focus_context = True
        if in_focus_context and local == 'Speed':
            try:
                speed = float((elem.text or '').strip())
            except ValueError:
                continue
            if speed > 0:
                return 'forward'
            if speed < 0:
                return 'backward'
            return 'stop'  # speed == 0 means stop
    return None


# ---------------------------------------------------------------------------
# Camera session / authentication helpers
# ---------------------------------------------------------------------------

def _compute_dahua_hash(username, password, random_str, realm):
    """Dahua 'Default' hash extracted from the camera's own web JS bundle:

        pwd1 = MD5(username + ':' + realm + ':' + password)   # full realm, WITH colons
        hash = MD5(username + ':' + random + ':' + pwd1)      # MD5 returns upper-hex
    """
    pwd1 = hashlib.md5(f'{username}:{realm}:{password}'.encode()).hexdigest().upper()
    return hashlib.md5(f'{username}:{random_str}:{pwd1}'.encode()).hexdigest().upper()


def _dahua_login(session, username, password):
    """Two-step Dahua JSON-RPC login (web interface on /RPC2_Login).

    Step 1 — send empty password to obtain realm + random challenge.
    Step 2 — send MD5 hash and establish the authenticated session cookie.
    Returns True on success.
    """
    login_url = f'{CAMERA_URL}/RPC2_Login'
    try:
        r1 = session.post(
            login_url,
            json={'method': 'global.login',
                  'params': {'userName': username, 'password': '', 'clientType': 'Web5.0'},
                  'id': 1},
            timeout=10,
        )
        r1_data = r1.json()
        params = r1_data.get('params', {})
        realm = params.get('realm', '')
        random_str = params.get('random', '')
        # The session ID returned by step 1 MUST be echoed back as a top-level
        # 'session' key in step 2; omitting it triggers "login challenge!" (code 268632079).
        session_id = r1_data.get('session', '')
        logging.debug('Dahua login step 1: realm=%s random=%s session=%s', realm, random_str, session_id)
    except Exception as exc:
        logging.error('Dahua login step 1 (challenge) failed: %s', exc)
        return False

    pwd_hash = _compute_dahua_hash(username, password, random_str, realm)
    try:
        r2 = session.post(
            login_url,
            json={
                'method': 'global.login',
                'params': {
                    'userName': username,
                    'password': pwd_hash,
                    'clientType': 'Web5.0',
                    'realm': realm,
                    'random': random_str,
                    'passwordType': 'Default',
                    'authorityType': 'Default',
                },
                'id': 5,
                'session': session_id,
            },
            timeout=10,
        )
        data = r2.json()
        if data.get('result'):
            logging.info('Dahua JSON-RPC login successful — session cookie stored')
            return True
        logging.error('Dahua JSON-RPC login rejected by camera: %s', data)
        return False
    except Exception as exc:
        logging.error('Dahua login step 2 (authenticate) failed: %s', exc)
        return False


def _init_camera_session(username, password, auth_type):
    """Configure proxy-level auth for non-Dahua modes (digest / basic).

    For Dahua mode the browser handles the full two-step JSON-RPC login itself
    through the transparent proxy.  The proxy just strips the Domain attribute
    from Set-Cookie responses so the browser's session cookie binds to the
    proxy's IP instead of the camera's IP.
    """
    global _proxy_auth
    if auth_type == 'digest':
        _proxy_auth = HTTPDigestAuth(username, password)
        logging.info('HTTP Digest auth configured (user: %s)', username)
    elif auth_type == 'basic':
        _proxy_auth = HTTPBasicAuth(username, password)
        logging.info('HTTP Basic auth configured (user: %s)', username)
    elif auth_type == 'dahua':
        # No proxy-level auth injection — the browser’s JS does the two-step
        # Dahua challenge-response natively.  The proxy only needs to strip
        # Domain from Set-Cookie headers (done in _rewrite_response_header) so
        # the session cookie is stored for the proxy host, not the camera host.
        logging.info(
            'Dahua mode: browser will complete the JSON-RPC login through the '
            'transparent proxy (Domain rewriting active).'
        )


# ---------------------------------------------------------------------------
# Response header rewriting
# ---------------------------------------------------------------------------

def _rewrite_response_header(name, value):
    """Rewrite Set-Cookie and Location headers to replace camera host with proxy host."""
    if name.lower() == 'set-cookie':
        # Remove Domain attribute so the browser binds the cookie to the proxy host,
        # not the camera's IP. Without this the session cookie is never sent back to
        # the proxy on subsequent requests.
        value = re.sub(r';\s*[Dd]omain=[^;,]+', '', value)
        return value
    if name.lower() == 'location':
        # Rewrite absolute redirects pointing to the camera so they stay on the proxy.
        value = re.sub(
            r'https?://' + re.escape(CAMERA_HOST) + r'(:\d+)?',
            '',
            value,
        )
        return value
    return value


class OnvifProxyHandler(http.server.BaseHTTPRequestHandler):
    def _proxy_request(self, body=None):
        target = urllib.parse.urljoin(CAMERA_URL, self.path)
        # Forward all client headers except hop-by-hop ones, then set Host to camera.
        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ('host', 'content-length', 'transfer-encoding', 'connection', 'authorization')
        }
        headers['Host'] = f'{CAMERA_HOST}:{CAMERA_PORT}'

        if body is None:
            body = b''

        logging.info('Proxy %s %s', self.command, self.path)
        if debug_mode:
            logging.debug('Request headers: %s', dict(self.headers))
            if body:
                logging.debug('Request body: %s', body.decode('utf-8', errors='replace'))

        try:
            # Use plain requests (no session) so the proxy never injects its own
            # cookies into browser requests.  The browser's Cookie header is
            # forwarded as-is; _proxy_auth adds HTTP Digest/Basic auth when
            # configured (digest / basic modes).
            response = requests.request(
                method=self.command,
                url=target,
                headers=headers,
                data=body,
                allow_redirects=False,
                timeout=10,
                auth=_proxy_auth,
            )
        except requests.RequestException as exc:
            logging.error('Erreur de proxy vers la caméra : %s', exc)
            self.send_error(502, 'Bad gateway')
            return None

        if debug_mode:
            logging.debug('Response status: %s', response.status_code)
            logging.debug('Response headers: %s', dict(response.headers))
            logging.debug('Response body: %s', response.content.decode('utf-8', errors='replace'))

        return response

    def _execute_motor_command(self, direction):
        """Exécute une commande moteur.
        
        Args:
            direction: 'forward', 'backward', 'stop', 'calibrate'
        
        Returns:
            dict: Résultat de la commande
        """
        if not motor.is_available():
            return {'error': 'Moteur non disponible'}
        
        try:
            if direction == 'forward':
                motor.move_forward()
                return {'direction': direction, 'status': 'ok'}
            elif direction == 'backward':
                motor.move_backward()
                return {'direction': direction, 'status': 'ok'}
            elif direction == 'stop':
                motor.stop()
                return {'direction': direction, 'status': 'ok'}
            elif direction == 'calibrate':
                result = motor.calibrate()
                return {'direction': direction, 'result': result, 'status': 'ok'}
            else:
                return {'error': f'Direction invalide: {direction}'}
        except Exception as exc:
            return {'error': str(exc)}
    
    def _send_json_response(self, data, status_code=200):
        """Envoie une réponse JSON."""
        json_data = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(json_data)))
        self.send_header('Access-Control-Allow-Origin', '*')  # Pour permettre l'accès depuis webapp
        self.end_headers()
        self.wfile.write(json_data)
    
    def _get_motor_status(self):
        """Retourne l'état complet du moteur."""
        if not motor.is_available():
            return {
                'available': False,
                'message': 'Moteur non disponible'
            }
        
        try:
            limit_status = motor.get_limit_switches_status()
            encoder_stats = motor.get_encoder_stats()
            return {
                'available': True,
                'limit_switches': limit_status,
                'can_move_forward': motor.can_move_forward(),
                'can_move_backward': motor.can_move_backward(),
                'encoder': encoder_stats
            }
        except Exception as exc:
            return {'error': str(exc)}
    
    def _get_encoder_info(self):
        """Retourne les informations détaillées de l'encodeur."""
        if not motor.is_available():
            return {
                'available': False,
                'message': 'Moteur non disponible'
            }
        
        try:
            return motor.get_encoder_stats()
        except Exception as exc:
            return {'error': str(exc)}
    
    def _intercept_focus(self, body):
        direction = _get_focus_direction(body)
        if direction is None:
            return False

        if test_mode:
            logging.info('[TEST MODE] Commande PTZ interceptée : %s (moteur non contrôlé)', direction)
            return True

        if direction == 'stop':
            if motor.is_available():
                motor.stop()
                logging.info('Commande focus stop : moteur arrêté')
            return False # Let stop commands pass through to the camera as well, in case it needs to do additional processing

        if not motor.is_available():
            logging.warning('Commande focus interceptée (%s) mais le moteur n est pas disponible', direction)
            return False

        logging.info('Commande focus interceptée : %s -> moteur %s', direction, direction)
        if direction == 'forward':
            motor.move_forward()
        else:
            motor.move_backward()
        return True

    def do_GET(self):
        logging.info('Received GET %s', self.path)
        if debug_mode:
            logging.debug('GET headers: %s', dict(self.headers))
        
        # API endpoints pour les stats du moteur
        if self.path == '/api/motor/status':
            self._send_json_response(self._get_motor_status())
            return
        elif self.path == '/api/motor/encoder':
            self._send_json_response(self._get_encoder_info())
            return
        elif self.path.startswith('/api/'):
            self._send_json_response({'error': 'Endpoint non trouvé'}, 404)
            return
        
        response = self._proxy_request()
        if response is None:
            return
        body = _rewrite_body_ips(
            response.content,
            response.headers.get('Content-Type', ''),
            self.client_address[0],
        )
        self.send_response(response.status_code)
        for name, value in response.headers.items():
            if name.lower() in ('content-length', 'transfer-encoding', 'connection'):
                continue
            self.send_header(name, _rewrite_response_header(name, value))
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        logging.info('Received POST %s', self.path)
        if debug_mode:
            logging.debug('POST headers: %s', dict(self.headers))
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b''

        if debug_mode and body:
            logging.debug('POST body: %s', body.decode('utf-8', errors='replace'))
        
        # API endpoint pour contrôler le moteur
        if self.path == '/api/motor/move':
            try:
                data = json.loads(body) if body else {}
                direction = data.get('direction')
                if not direction:
                    self._send_json_response({'error': 'Paramètre direction requis'}, 400)
                    return
                
                if direction not in ('forward', 'backward', 'stop', 'calibrate'):
                    self._send_json_response({'error': 'Direction invalide'}, 400)
                    return
                
                result = self._execute_motor_command(direction)
                if 'error' in result:
                    self._send_json_response(result, 500)
                else:
                    self._send_json_response(result)
                return
            except json.JSONDecodeError:
                self._send_json_response({'error': 'JSON invalide'}, 400)
                return
            except Exception as exc:
                self._send_json_response({'error': str(exc)}, 500)
                return
        elif self.path == '/api/motor/limit_switches':
            try:
                data = json.loads(body) if body else {}
                enabled = data.get('enabled', True)
                
                if not motor.is_available():
                    self._send_json_response({'error': 'Motor non disponible'}, 503)
                    return
                
                motor.set_limit_switches_enabled(enabled)
                
                self._send_json_response({
                    'success': True,
                    'enabled': motor.get_limit_switches_enabled(),
                    'message': f"Capteurs de fin de course {'activés' if enabled else 'désactivés'}"
                })
                return
            except json.JSONDecodeError:
                self._send_json_response({'error': 'JSON invalide'}, 400)
                return
            except Exception as exc:
                self._send_json_response({'error': str(exc)}, 500)
                return
        elif self.path.startswith('/api/'):
            self._send_json_response({'error': 'Endpoint non trouvé'}, 404)
            return

        # Log SOAP action in test mode for visibility
        if test_mode and body:
            soap_action = _get_soap_action(body)
            if soap_action:
                logging.info('[TEST MODE] Commande SOAP : %s', soap_action)

        if body and self._intercept_focus(body):
            self.send_response(200)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        response = self._proxy_request(body=body)
        if response is None:
            return
        resp_body = _rewrite_body_ips(
            response.content,
            response.headers.get('Content-Type', ''),
            self.client_address[0],
        )
        self.send_response(response.status_code)
        for name, value in response.headers.items():
            if name.lower() in ('content-length', 'transfer-encoding', 'connection'):
                continue
            self.send_header(name, _rewrite_response_header(name, value))
        self.send_header('Content-Length', str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)

    def log_message(self, format, *args):
        logging.info('%s - %s', self.address_string(), format % args)


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main():
    global debug_mode, test_mode
    parser = argparse.ArgumentParser(description='ONVIF gateway proxy avec interception focus')
    parser.add_argument('--debug', action='store_true', help='Activer le mode debug pour GET/POST')
    parser.add_argument('--test', action='store_true', help='Mode test : afficher les commandes PTZ sans contacter la caméra ou contrôler le moteur')
    parser.add_argument('--camera-user', default='', help='Nom d\'utilisateur pour s\'authentifier auprès de la caméra')
    parser.add_argument('--camera-password', default='', help='Mot de passe pour s\'authentifier auprès de la caméra')
    parser.add_argument(
        '--camera-auth-type',
        choices=['digest', 'basic', 'dahua'],
        default='dahua',
        help=(
            'Type d\'authentification : '
            'dahua = JSON-RPC Dahua (interface web, défaut), '
            'digest = HTTP Digest (ONVIF/SOAP), '
            'basic = HTTP Basic'
        ),
    )
    args = parser.parse_args()

    if args.debug:
        debug_mode = True
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug('Mode debug activé')

    if args.test:
        test_mode = True
        logging.info('Mode test activé : les commandes PTZ seront affichées sans être exécutées')

    if args.camera_user and args.camera_password:
        _init_camera_session(args.camera_user, args.camera_password, args.camera_auth_type)
    else:
        logging.warning(
            'Aucun identifiant caméra fourni — les requêtes sont transmises sans authentification proxy.\n'
            '  Utilisez --camera-user / --camera-password (et --camera-auth-type dahua pour l\'interface web Dahua).'
        )

    if not motor.is_available():
        logging.warning('Le moteur n est pas disponible. Le proxy est néanmoins actif.')

    discovery_thread = threading.Thread(
        target=run_ws_discovery,
        args=(LISTEN_PORT,),
        daemon=True,
        name='ws-discovery',
    )
    discovery_thread.start()

    with _ReusableTCPServer(('0.0.0.0', LISTEN_PORT), OnvifProxyHandler) as httpd:
        httpd.allow_reuse_address = True
        httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        logging.info('ONVIF proxy démarré sur le port %s', LISTEN_PORT)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logging.info('Arrêt du proxy')


if __name__ == '__main__':
    main()
