import os
import random
import json
import uuid
import logging
import tornado.httpserver
import tornado.auth
import tornado.web
import tornado.websocket
import tornado.ioloop
import tornado.gen

import tornadoredis

import tornado.options
tornado.options.parse_command_line()


PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

c = tornadoredis.Client()
c.connect()

@tornado.gen.engine
def init_data():
    with c.pipeline() as pipe:
        chaters = []
        pipe.set('waiters', json.dumps(chaters))
        yield tornado.gen.Task(pipe.execute)

@tornado.gen.engine
def change_chater(user):
    prev_chater = yield tornado.gen.Task(c.get, user['uuid'])
    waiters = yield tornado.gen.Task(c.get, 'waiters')
    waiters = json.loads(waiters)
    next_chater = ''
    if waiters:
        next_chater = random.choice(waiters)
    if next_chater and next_chater != user['uuid']:
        data = {}
        data['status'] = 'chat_started'
        data['message'] = 'start'
        c.publish(next_chater, json.dumps(data))
        c.publish(user['uuid'], json.dumps(data))
        waiters.remove(next_chater)
    elif user['uuid'] not in waiters:
        waiters.append(user['uuid'])
    if prev_chater and prev_chater not in waiters:
        waiters.append(prev_chater)

    logging.info(waiters)
    with c.pipeline() as pipe:
        pipe.set('waiters', json.dumps(waiters))
        pipe.set(user['uuid'], next_chater)
        if next_chater:
            pipe.set(next_chater, user['uuid'])
        yield tornado.gen.Task(pipe.execute)

class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        user = self.get_secure_cookie('user')
        if user:
            return json.loads(user)
        return None

class MainHandler(BaseHandler):

    def get(self):
        if self.get_current_user():
            self.redirect('/chat')
        else:
            self.render('index.html', title='PubSub + WebSocket Demo')

class ChatHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render('personal_chat.html', title='PubSub + WebSocket Demo')

class RoomHandler(BaseHandler):

    def get(self, room):
        self.render('room.html', room=room)

class StartChatHandler(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self):
        user = self.get_current_user()
        change_chater(user)
        self.finish()


class NewMessage(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self):
        data = {}
        data['message'] = self.get_argument('message')
        data['status'] = 'message'
        user = self.get_current_user()
        chater = yield tornado.gen.Task(c.get,  user['uuid'])
        if chater:
            c.publish(chater, json.dumps(data))
        self.finish()

class RoomMessage(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self, room):
        data = {}
        user = self.get_current_user()
        data['message'] = self.get_argument('message')
        data['status'] = 'message'
        data['user'] = user['uuid']
        c.publish(room, json.dumps(data))
        self.finish()

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
        self.redirect(self.get_argument('next', '/chat'))
        # Save the user with, e.g., set_secure_cookie()


class MessagesCatcher(BaseHandler, tornado.websocket.WebSocketHandler):

    @tornado.gen.engine
    def open(self):
        user = self.get_current_user()
        change_chater(user)
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
        logging.info(msg)
        if msg.kind == 'message':
            self.write_message(json.loads(msg.body))
        if msg.kind == 'disconnect':
            # Do not forget to restart a listen loop
            # after a successful reconnect attempt.

            # Do not try to reconnect, just send a message back
            # to the client and close the client connection
            self.close()

    @tornado.gen.engine
    def on_close(self):
        user = self.get_current_user()
        chater = yield tornado.gen.Task(c.get,  user['uuid'])
        if chater:
            data = {}
            data['status'] = 'chat_ended'
            data['message'] = 'start'
            c.publish(chater, json.dumps(data))
            with c.pipeline() as pipe:
                waiters = yield tornado.gen.Task(c.get, 'waiters')
                waiters = json.loads(waiters)
                if chater and chater not in waiters:
                    waiters.append(chater)
                pipe.set('waiters', json.dumps(waiters))
                pipe.set(user['uuid'], '')
                pipe.set(chater, '')
                yield tornado.gen.Task(pipe.execute)
        if self.client.subscribed:
            self.client.unsubscribe(user['uuid'])
            self.client.disconnect()

class RoomMessagesCatcher(BaseHandler, tornado.websocket.WebSocketHandler):

    @tornado.gen.engine
    def open(self, room):
        user = self.get_current_user()
        self.room = room
        self.listen()

    @tornado.gen.engine
    def listen(self):
        user = self.get_current_user()
        self.client = tornadoredis.Client()
        if user:
            self.client.connect()
            yield tornado.gen.Task(self.client.subscribe, self.room)
            self.client.listen(self.on_message)

    def on_message(self, msg):
        if msg.kind == 'message':
            self.write_message(json.loads(msg.body))
        if msg.kind == 'disconnect':
            # Do not forget to restart a listen loop
            # after a successful reconnect attempt.

            # Do not try to reconnect, just send a message back
            # to the client and close the client connection
            self.close()

    @tornado.gen.engine
    def on_close(self):
        if self.client.subscribed:
            self.client.unsubscribe(self.room)
            self.client.disconnect()

settings = {
    'cookie_secret': '151068a7abbb45b82fcaadc0eed3dd4e',
    'login_url': '/login',
    'template_path': TEMPLATE_PATH
}

application = tornado.web.Application([
    (r'/', MainHandler),
    (r'/chat', ChatHandler),
    (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': STATIC_PATH}),
    (r'/msg', NewMessage),
    (r'/room_msg/(.*)', RoomMessage),
    (r'/login', GoogleLoginHandler),
    (r'/track', MessagesCatcher),
    (r'/room_track/(.*)', RoomMessagesCatcher),
    (r'/room/(.*)', RoomHandler),
    (r'/change_chater', StartChatHandler),
], **settings)

if __name__ == '__main__':
    init_data()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    print 'Demo is runing at 0.0.0.0:8888\nQuit the demo with CONTROL-C'
    tornado.ioloop.IOLoop.instance().start()
