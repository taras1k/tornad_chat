import os
from keys import COOKIE_SECRET, RECAPTCHA_PUBLIC, RECAPTCHA_PRIVATE

#URL = '0.0.0.0:8888'
URL = 'chat.nek.me'

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

settings = {
    'cookie_secret': COOKIE_SECRET,
    'login_url': '/login',
    'template_path': TEMPLATE_PATH,
    'recaptcha_private': RECAPTCHA_PRIVATE,
    'recaptcha_public': RECAPTCHA_PUBLIC,
    'ssl_options': {'certfile': '/etc/nginx/ssl/cert.pem',
                    'keyfile': '/etc/nginx/ssl/cert.pem'}
}
