import requests, re
import json
from config import YANDEX_RCA_URL
from keys import YANDEX_RCA_KEY

GRUBER_URLINTEXT_PAT = re.compile(ur'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')

def yancex_rca_formater(link_obj):
    payload = {'url': link_obj.group(0), 'key': YANDEX_RCA_KEY}
    r = requests.get(YANDEX_RCA_URL, params=payload)
    return '[media_content]%s[/media_content]' % r.text

def format_message(message):
    return re.sub(GRUBER_URLINTEXT_PAT, yancex_rca_formater, message)
