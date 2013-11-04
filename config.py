import os
from keys import COOKIE_SECRET, RECAPTCHA_PUBLIC, RECAPTCHA_PRIVATE
from tornado_utils.tornado_static import (
  StaticURL, Static, PlainStaticURL, PlainStatic)

UI_MODULES = {}
UI_MODULES['Static'] = PlainStatic
UI_MODULES['StaticURL'] = PlainStaticURL

#URL = '0.0.0.0:8888'
URL = 'chat.nek.me'
YANDEX_RCA_URL = 'http://rca.yandex.com'

MAX_HISTORY_MESSAGES = 10

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

settings = dict(
    cookie_secret=COOKIE_SECRET,
    login_url='/login',
    template_path=TEMPLATE_PATH,
    recaptcha_private=RECAPTCHA_PRIVATE,
    recaptcha_public=RECAPTCHA_PUBLIC,
    ssl_options=dict(certfile='/etc/nginx/ssl/cert.pem',
                    keyfile='/etc/nginx/ssl/cert.pem'),
    static_path=STATIC_PATH,
    ui_modules=UI_MODULES,
    UGLIFYJS_LOCATION='~/bin/uglifyjs',
    CLOSURE_LOCATION="static/compiler.jar",
    YUI_LOCATION="static/yuicompressor-2.4.2.jar",
)
