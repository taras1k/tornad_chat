import os
from keys import COOKIE_SECRET, TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET,\
    FACEBOOK_API_KEY, FACEBOOK_SECRET

URL = '0.0.0.0:8888'
#URL = 'chat.nek.me'

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

settings = {
    'cookie_secret': COOKIE_SECRET,
    'login_url': '/login_fb',
    'template_path': TEMPLATE_PATH,
    'twitter_consumer_key': TWITTER_CONSUMER_KEY,
    'twitter_consumer_secret': TWITTER_CONSUMER_SECRET,
    'facebook_api_key': FACEBOOK_API_KEY,
    'facebook_secret': FACEBOOK_SECRET
}
