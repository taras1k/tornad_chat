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
from mongotor.database import Database
from models import User, Room, Waiters

tornado.options.parse_command_line()

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

c = tornadoredis.Client(selected_db='massages')
c.connect()
Database.connect(['localhost:27017'], 'anon_chat')

class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie('user')

    def db_response(self, response):
        logging.info(response)


    @property
    def user(self):
        if not hasattr(self, '_user'):
            user_id = self.get_current_user()
            self._user = User.objects.find_one({'uuid': user_id},
                                               self.db_response)
            if not self._user:
                self._user = User()
                self._user.uuid = user_id
                self._user.chater = ''
                self._user.save()
        logging.info(self._user)
        return self._user

    @tornado.gen.engine
    def change_chater(self):
        prev_chater = self.user.chater
        waiters = yield tornado.gen.Task(Waiters.objects.find_one, {})
        logging.info(waiters._id)
        next_chater = ''
        if not waiters:
            waiters = Waiters()
            waiters.queue = []
            yield tornado.gen.Task(waiters.save)
        queue = waiters.queue[:]
        if queue:
            next_chater = random.choice(queue)
        if next_chater and next_chater != self.user.uuid:
            data = {}
            data['status'] = 'chat_started'
            data['message'] = 'start'
            c.publish(next_chater, json.dumps(data))
            c.publish(self.user.uuid, json.dumps(data))
            queue.remove(next_chater)
        elif self.user.uuid not in queue:
            queue.append(self.user.uuid)
        if prev_chater and prev_chater not in waiters.queue:
            queue.append(prev_chater)
        waiters.queue = queue
        logging.info(waiters.queue)
        yield tornado.gen.Task(self.user.update)
        yield tornado.gen.Task(waiters.update, multi=True, upsert=True)

class MainHandler(BaseHandler):

    def get(self):
        if self.user:
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
        self.change_chater()
        self.finish()


class NewMessage(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self):
        data = {}
        data['message'] = self.get_argument('message')
        data['status'] = 'message'
        if self.user.chater:
            c.publish(self.user.chater, json.dumps(data))
        self.finish()

class RoomMessage(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self, room):
        data = {}
        data['message'] = self.get_argument('message')
        data['status'] = 'message'
        data['user'] = self.user.uuid
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
        self.set_secure_cookie('user', uuid.uuid4().get_hex())
        self.redirect(self.get_argument('next', '/chat'))
        # Save the user with, e.g., set_secure_cookie()


class MessagesCatcher(BaseHandler, tornado.websocket.WebSocketHandler):

    @tornado.gen.engine
    def open(self):
        self.change_chater()
        self.listen()

    @tornado.gen.engine
    def listen(self):
        self.client = tornadoredis.Client()
        if self.user:
            self.client.connect()
            chanel_name = self.user.uuid
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
        if self.user.chater:
            data = {}
            data['status'] = 'chat_ended'
            data['message'] = 'start'
            c.publish(self.user.chater, json.dumps(data))
            waiters = yield tornado.gen.Task(Waiters.objects.find_one, {})
            if not waiters:
                waiters = Waiters()
                waiters.queue = []
                yield tornado.gen.Task(waiters.save)
            if self.user.uuid in waiters.queue:
                waiters.queue.remove(self.user.uuid)
            if self.user.chater not in queue:
                queue.append(self.user.chater)
            self.user.chater = ''
            yield tornado.gen.Task(self.user.update)
            yield tornado.gen.Task(waiters.update)
        if self.client.subscribed:
            self.client.unsubscribe(self.user['uuid'])
            self.client.disconnect()

class RoomMessagesCatcher(BaseHandler, tornado.websocket.WebSocketHandler):

    @tornado.gen.engine
    def open(self, room):
        self.room = room
        self.listen()

    @tornado.gen.engine
    def listen(self):
        self.client = tornadoredis.Client()
        if self.user:
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
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    print 'Demo is runing at 0.0.0.0:8888\nQuit the demo with CONTROL-C'
    tornado.ioloop.IOLoop.instance().start()
