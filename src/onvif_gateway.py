#!/usr/bin/env python3
"""Proxy HTTP simple pour relayer les requêtes ONVIF du réseau local vers la caméra et intercepter focus+ / focus-."""

import argparse
import http.server
import logging
import socketserver
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from motor_driver import MotorDriver

CAMERA_HOST = '192.168.1.108'
CAMERA_PORT = 80
CAMERA_URL = f'http://{CAMERA_HOST}:{CAMERA_PORT}'

MOTOR_FORWARD_PIN = 20
MOTOR_BACKWARD_PIN = 21
LISTEN_PORT = 80

debug_mode = False

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

motor = MotorDriver(forward_pin=MOTOR_FORWARD_PIN, backward_pin=MOTOR_BACKWARD_PIN)
if motor.is_available():
    logging.info('Motor driver initialisé')
else:
    logging.warning('Motor driver non disponible : le proxy continuera à relayer les requêtes sans piloter le moteur')


def _xml_contains_focus_command(body_bytes):
    try:
        root = ET.fromstring(body_bytes)
    except ET.ParseError:
        return None

    for elem in root.iter():
        tag = elem.tag
        if tag.endswith('FocusMove') or tag.endswith('Focus') or tag.endswith('Zoom'):
            return elem
    return None


def _get_focus_direction(body_bytes):
    try:
        root = ET.fromstring(body_bytes)
    except ET.ParseError:
        return None

    for elem in root.iter():
        tag = elem.tag
        if tag.endswith('Zoom'):
            value = elem.attrib.get('x') or elem.text
            if value is None:
                continue
            try:
                zoom = float(value)
            except ValueError:
                continue
            return 'forward' if zoom > 0 else 'backward' if zoom < 0 else None

        if tag.endswith('FocusMove') or tag.endswith('Focus'):
            # focus commands are usually incremental, assume focus+ -> forward, focus- -> backward
            text = (elem.text or '').strip().lower()
            if '+' in text:
                return 'forward'
            if '-' in text:
                return 'backward'
    return None


class OnvifProxyHandler(http.server.BaseHTTPRequestHandler):
    def _proxy_request(self, body=None):
        target = urllib.parse.urljoin(CAMERA_URL, self.path)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ('host', 'content-length')}
        headers['Host'] = f'{CAMERA_HOST}:{CAMERA_PORT}'

        if body is None:
            body = b''

        logging.info('Proxy %s %s', self.command, self.path)
        if debug_mode:
            logging.debug('Request headers: %s', dict(self.headers))
            if body:
                logging.debug('Request body: %s', body.decode('utf-8', errors='replace'))

        try:
            response = requests.request(
                method=self.command,
                url=target,
                headers=headers,
                data=body,
                allow_redirects=False,
                timeout=10,
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

    def _intercept_focus(self, body):
        direction = _get_focus_direction(body)
        if direction is None:
            return False

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
        response = self._proxy_request()
        if response is None:
            return
        self.send_response(response.status_code)
        for name, value in response.headers.items():
            if name.lower() in ('content-length', 'transfer-encoding', 'connection'):
                continue
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(response.content)))
        self.end_headers()
        self.wfile.write(response.content)

    def do_POST(self):
        logging.info('Received POST %s', self.path)
        if debug_mode:
            logging.debug('POST headers: %s', dict(self.headers))
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b''

        if debug_mode and body:
            logging.debug('POST body: %s', body.decode('utf-8', errors='replace'))

        if body:
            self._intercept_focus(body)

        response = self._proxy_request(body=body)
        if response is None:
            return
        self.send_response(response.status_code)
        for name, value in response.headers.items():
            if name.lower() in ('content-length', 'transfer-encoding', 'connection'):
                continue
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(response.content)))
        self.end_headers()
        self.wfile.write(response.content)

    def log_message(self, format, *args):
        logging.info('%s - %s', self.address_string(), format % args)


def main():
    global debug_mode
    parser = argparse.ArgumentParser(description='ONVIF gateway proxy avec interception focus')
    parser.add_argument('--debug', action='store_true', help='Activer le mode debug pour GET/POST')
    args = parser.parse_args()

    if args.debug:
        debug_mode = True
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug('Mode debug activé')

    if not motor.is_available():
        logging.warning('Le moteur n est pas disponible. Le proxy est néanmoins actif.')

    with socketserver.TCPServer(('0.0.0.0', LISTEN_PORT), OnvifProxyHandler) as httpd:
        logging.info('ONVIF proxy démarré sur le port %s', LISTEN_PORT)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logging.info('Arrêt du proxy')


if __name__ == '__main__':
    main()
