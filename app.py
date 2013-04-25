import os
import random
import json
import uuid
import tornado.httpserver
import tornado.auth
import tornado.web
import tornado.websocket
import tornado.ioloop
import tornado.gen

import tornadoredis

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

c = tornadoredis.Client()
c.connect()

@tornado.gen.engine
def init_data():
    with c.pipeline() as pipe:
        pipe.set('waiters', 1)
        yield tornado.gen.Task(pipe.execute)

class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        user = self.get_secure_cookie('user')
        if user:
            return json.loads(user)
        return None

class MainHandler(BaseHandler):

    def get(self):
        self.render('index.html', title='PubSub + WebSocket Demo')


class StartChatHandler(BaseHandler):

    @tornado.web.authenticated
    @tornado.gen.engine
    def get(self):
        status = 'unjoined'
        user = self.get_current_user()
        prev_chater = self.get_secure_cookie('chater')
        waiters = yield tornado.gen.Task(c.get, 'waiters')
        self.write(status)
#        if waiters:
#            next_chater = random.choice(waiters)
#            waiters.remove(next_chater)
#            self.set_secure_cookie('chater', next_chater)
#            status = 'joined'
#        elif user['uui'] not in waiters:
#            waiters.append(user['uuid'])
#        if prev_chater:
#            waiters.append(prev_chater)
#        with c.pipeline() as pipe:
#            pipe.set('waiters', waiters)
#            yield tornado.gen.Task(pipe.execute)


class NewMessage(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        message = self.get_argument('message')
        chater = self.get_secure_cookie('chater')
        if chater:
            c.publish(chater, message)
        #self.set_header('Content-Type', 'text/plain')
        #self.write('sent: %s' % (message,))

class GoogleLoginHandler(BaseHandler, tornado.auth.GoogleMixin):

    @tornado.web.asynchronous
    def get(self):
        if self.get_argument('openid.mode', None):
            self.get_authenticated_user(self._on_auth)
            return
        self.authenticate_redirect()

    def _on_auth(self, user):
        if not user:
            self.authenticate_redirect()
            return
        user['uuid'] = uuid.uuid4().get_hex()
        self.set_secure_cookie('user', json.dumps(user))
        self.redirect(self.get_argument('next', '/'))
        # Save the user with, e.g., set_secure_cookie()


class MessagesCatcher(BaseHandler, tornado.websocket.WebSocketHandler):

    def __init__(self, *args, **kwargs):
        super(MessagesCatcher, self).__init__(*args, **kwargs)
        self.listen()

    @tornado.gen.engine
    def listen(self):
        user = self.get_current_user()
        self.client = tornadoredis.Client()
        if user:
            self.client.connect()
            chanel_name = user['uuid']
            yield tornado.gen.Task(self.client.subscribe, chanel_name)
            self.client.listen(self.on_message)

    def on_message(self, msg):
        if msg.kind == 'message':
            self.write_message(msg.body)
        if msg.kind == 'disconnect':
            # Do not forget to restart a listen loop
            # after a successful reconnect attempt.

            # Do not try to reconnect, just send a message back
            # to the client and close the client connection
            self.write_message('The connection terminated '
                               'due to a Redis server error.')
            self.close()

    def on_close(self):
        if self.client.subscribed:
            self.client.unsubscribe(self.get_current_user()['uuid'])
            self.client.disconnect()

settings = {
    'cookie_secret': '151068a7abbb45b82fcaadc0eed3dd4e',
    'login_url': '/login',
    'template_path': TEMPLATE_PATH
}

application = tornado.web.Application([
    (r'/', MainHandler),
    (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': STATIC_PATH}),
    (r'/msg', NewMessage),
    (r'/login', GoogleLoginHandler),
    (r'/track', MessagesCatcher),
    (r'/change_chater', StartChatHandler),
], **settings)

if __name__ == '__main__':
    init_data()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    print 'Demo is runing at 0.0.0.0:8888\nQuit the demo with CONTROL-C'
    tornado.ioloop.IOLoop.instance().start()
