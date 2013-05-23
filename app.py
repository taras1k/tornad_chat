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
from tornado.escape import json_encode
from mongotor.database import Database
from config import URL
from models import User, Room, Waiters

tornado.options.parse_command_line()

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))
STATIC_PATH = os.path.join(PROJECT_PATH, 'static')
TEMPLATE_PATH = os.path.join(PROJECT_PATH, 'templates')

c = tornadoredis.Client(selected_db='massages')
c.connect()
Database.connect(['localhost:27017'], 'anon_chat')

@tornado.gen.engine
def init_data():
    waiters = yield tornado.gen.Task(Waiters.objects.find, {})
    for waiter in waiters:
        yield tornado.gen.Task(waiter.remove)
    users = yield tornado.gen.Task(User.objects.find, {})
    for user in users:
        yield tornado.gen.Task(user.remove)
    rooms = yield tornado.gen.Task(Room.objects.find, {})
    for room in rooms:
        yield tornado.gen.Task(room.remove)

class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie('user')

    @tornado.gen.engine
    def user(self, callback):
        if not hasattr(self, '_user'):
            user_id = self.get_current_user()
            logging.info(user_id)
            if user_id:
                self._user = yield tornado.gen.Task(User.objects.find_one,
                                                    {'uuid': user_id})
                if not self._user:
                    self._user = User()
                    self._user.uuid = user_id
                    self._user.chater = ''
                    yield tornado.gen.Task(self._user.save)
            else:
                self._user = None
            logging.info(self._user)
        callback(self._user)


    @tornado.gen.engine
    def change_chater(self):
        user = yield tornado.gen.Task(self.user)
        prev_chater = user.chater
        waiters = yield tornado.gen.Task(Waiters.objects.find_one, {})
        next_chater = ''
        if not waiters:
            waiters = Waiters()
            waiters.queue = []
            yield tornado.gen.Task(waiters.save)
        queue = waiters.queue[:]
        logging.info(queue)
        if queue:
            next_chater = random.choice(queue)
        logging.info(next_chater)
        logging.info(user.uuid)
        if next_chater and next_chater != user.uuid:
            data = {}
            data['status'] = 'chat_started'
            data['message'] = 'start'
            c.publish(next_chater, json.dumps(data))
            c.publish(user.uuid, json.dumps(data))
            user.chater = next_chater
            queue.remove(next_chater)
        elif user.uuid not in queue:
            queue.append(user.uuid)
        if prev_chater:
            chater = yield tornado.gen.Task(User.objects.find_one,
                                                {'uuid': prev_chater})
            if chater:
                chater.chater = ''
                yield tornado.gen.Task(chater.update)
            if prev_chater not in waiters.queue:
                queue.append(prev_chater)
        waiters.queue = queue
        yield tornado.gen.Task(user.update)
        yield tornado.gen.Task(waiters.update)

    def render_template(self, template_name, *kw):
        user = self.get_current_user()
        self.render(template_name, user=user, url=URL, *kw)


class MainHandler(BaseHandler):

    def get(self):
        user = self.get_current_user()
        if user:
            self.redirect('/chat')
        else:
            self.render_template('index.html', title='PubSub + WebSocket Demo')

class PopularRoomsHandler(BaseHandler):

    @tornado.gen.engine
    @tornado.web.asynchronous
    def get(self):
        rooms = yield tornado.gen.Task(Room.objects.find, {}, limit=20,
                                       sort=[('visitors', 'ASC')])
        popular_rooms = []
        for room in rooms:
            r = room.as_dict()
            r.pop('_id')
            popular_rooms.append(r)
        self.set_header('Content-Type', 'application/json')
        self.write(json_encode(popular_rooms))
        self.finish()

class ChatHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render_template('personal_chat.html')

class RoomHandler(BaseHandler):

    def get(self, room):
        self.render_template('room.html', room=room)

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
        user = yield tornado.gen.Task(self.user)
        data = {}
        data['message'] = self.get_argument('message')
        data['status'] = 'message'
        if user.chater:
            c.publish(user.chater, json.dumps(data))
        self.finish()

class RoomMessage(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self, room):
        user = yield tornado.gen.Task(self.user)
        data = {}
        data['message'] = self.get_argument('message')
        data['status'] = 'message'
        data['user'] = user.uuid
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
        self.set_secure_cookie('user', uuid.uuid4().get_hex(), domain=URL)
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
        user = yield tornado.gen.Task(self.user)
        if user:
            self.client.connect()
            chanel_name = user.uuid
            yield tornado.gen.Task(self.client.subscribe, chanel_name)
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
        user = yield tornado.gen.Task(self.user)
        if user.chater:
            data = {}
            data['status'] = 'chat_ended'
            data['message'] = 'start'
            c.publish(user.chater, json.dumps(data))
            waiters = yield tornado.gen.Task(Waiters.objects.find_one, {})
            if not waiters:
                waiters = Waiters()
                waiters.queue = []
                yield tornado.gen.Task(waiters.save)
            queue = waiters.queue[:]
            if user.uuid in queue:
                queue.remove(user.uuid)
            chater = yield tornado.gen.Task(User.objects.find_one,
                                                {'uuid': user.chater})
            if chater:
                chater.chater = ''
                yield tornado.gen.Task(chater.update)
            if user.chater not in queue:
                queue.append(user.chater)
            user.chater = ''
            yield tornado.gen.Task(user.update)
            waiters.queue = queue
            yield tornado.gen.Task(waiters.update)
        if self.client.subscribed:
            self.client.unsubscribe(user.uuid)
            self.client.disconnect()

class RoomMessagesCatcher(BaseHandler, tornado.websocket.WebSocketHandler):

    @tornado.gen.engine
    def open(self, room):
        self.room = yield tornado.gen.Task(Room.objects.find_one, {'name': room})
        if not self.room:
            self.room = Room()
            self.room.visitors = 0
            self.room.name = room
            yield tornado.gen.Task(self.room.save)
        self.room.visitors += 1
        yield tornado.gen.Task(self.room.update)
        self.listen()

    @tornado.gen.engine
    def listen(self):
        self.client = tornadoredis.Client()
        user = yield tornado.gen.Task(self.user)
        if user:
            self.client.connect()
            yield tornado.gen.Task(self.client.subscribe, self.room.name)
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
        self.room.visitors -= 1
        yield tornado.gen.Task(self.room.update)
        if self.client.subscribed:
            self.client.unsubscribe(self.room.name)
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
    (r'/popular_rooms', PopularRoomsHandler),
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
