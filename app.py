import os
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

class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        user = self.get_secure_cookie('user')
        if user:
            return user
        return None

class MainHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render('index.html', title='PubSub + WebSocket Demo')


class NewMessage(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        message = self.get_argument('message')
        user = self.get_current_user()
        c.publish('test_channel', '%s: %s' %(user, message))
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
        self.set_secure_cookie('user', str(user))
        self.redirect(self.get_argument('next', '/'))
        # Save the user with, e.g., set_secure_cookie()


class MessagesCatcher(tornado.websocket.WebSocketHandler):

    def __init__(self, *args, **kwargs):
        super(MessagesCatcher, self).__init__(*args, **kwargs)
        self.listen()

    @tornado.gen.engine
    def listen(self):
        self.client = tornadoredis.Client()
        self.client.connect()
        yield tornado.gen.Task(self.client.subscribe, 'test_channel')
        self.client.listen(self.on_message)

    def on_message(self, msg):
        if msg.kind == 'message':
            self.write_message(str(msg.body))
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
            self.client.unsubscribe('test_channel')
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
    (r'/track/', MessagesCatcher),
], **settings)

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    print 'Demo is runing at 0.0.0.0:8888\nQuit the demo with CONTROL-C'
    tornado.ioloop.IOLoop.instance().start()
