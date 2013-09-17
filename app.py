# -*- coding: utf-8 -*-
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
from recaptcha import RecaptchaClient, RecaptchaUnreachableError, RecaptchaException
from tornado.escape import json_encode
from mongotor.database import Database
from config import URL, STATIC_PATH, settings
from models import User, Room, Waiters

tornado.options.parse_command_line()


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
    waiters = Waiters()
    waiters.queue = []
    yield tornado.gen.Task(waiters.save)


class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie('user')

    @tornado.gen.engine
    def user(self, callback):
        if not hasattr(self, '_user'):
            user_id = self.get_current_user()
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
        callback(self._user)


    @tornado.gen.engine
    def change_chater(self):
        data = {}
        user = yield tornado.gen.Task(self.user)
        prev_chater = user.chater
        waiters = yield tornado.gen.Task(Waiters.objects.find_one, {})
        next_chater = ''
        queue = waiters.queue[:]
        if queue:
            next_chater = random.choice(queue)
        else:
            queue.append(user.uuid)
        if next_chater and next_chater != user.uuid:
            data['status'] = 'chat_started'
            data['message'] = 'start'
            c.publish(next_chater, json.dumps(data))
            c.publish(user.uuid, json.dumps(data))
            user.chater = next_chater
            queue.remove(next_chater)
            yield tornado.gen.Task(user.update)
            chater = yield tornado.gen.Task(User.objects.find_one,
                                                {'uuid': next_chater})
            if chater:
                chater.chater = user.uuid
                yield tornado.gen.Task(chater.update)
        elif user.uuid not in queue:
            queue.append(user.uuid)
        if prev_chater:
            chater = yield tornado.gen.Task(User.objects.find_one,
                                                {'uuid': prev_chater})
            if chater:
                data['status'] = 'chat_ended'
                data['message'] = 'stop'
                c.publish(chater.uuid, json.dumps(data))
                chater.chater = ''
                yield tornado.gen.Task(chater.update)
            if prev_chater not in waiters.queue:
                queue.append(prev_chater)
        waiters.queue = queue
        yield tornado.gen.Task(waiters.update)

    def render_template(self, template_name, **kw):
        user = self.get_current_user()
        self.render(template_name, user=user, url=URL, **kw)

class NotSupportedHandler(BaseHandler):

    def get(self):
        self.render_template('not_supported.html', title='Not supported')

class MainHandler(BaseHandler):

    def get(self):
        user = self.get_current_user()
        if user:
            self.set_secure_cookie('user', uuid.uuid4().get_hex())
            self.redirect(self.get_argument('next', '/chat'))
        else:
            self.render_template('index.html', title='Chat')

class LoginHandler(BaseHandler):

    def get(self):
        user = self.get_current_user()
        error = ''
        if user:
            self.set_secure_cookie('user', uuid.uuid4().get_hex())
            self.redirect(self.get_argument('next', '/chat'))
        else:
            recaptcha_client = RecaptchaClient(settings['recaptcha_private'],
                                               settings['recaptcha_public'])
            self.render_template('login.html', title='Chat',
                                 recaptcha=recaptcha_client, error=error)
    def post(self):
        recaptcha_response = self.get_argument('recaptcha_response_field')
        recaptcha_challenge = self.get_argument('recaptcha_challenge_field')
        recaptcha_client = RecaptchaClient(settings['recaptcha_private'],
                                           settings['recaptcha_public'])
        error = ''
        try:
            is_solution_correct = recaptcha_client.is_solution_correct(
                recaptcha_response,
                recaptcha_challenge,
                self.request.remote_ip,
                )
        except RecaptchaUnreachableError as exc:
             error = 'reCAPTCHA is unreachable; please try again later'
        except RecaptchaException as exc:
            error = exc
        else:
            if is_solution_correct:
                self.set_secure_cookie('user', uuid.uuid4().get_hex())
                self.redirect(self.get_argument('next', '/chat'))
            else:
                error = 'Invalid solution to CAPTCHA challenge'
                self.render_template('login.html', title='Chat',
                                     recaptcha=recaptcha_client, error=error)

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

class AllRoomsHandler(BaseHandler):

    @tornado.gen.engine
    @tornado.web.asynchronous
    def get(self):
        rooms = yield tornado.gen.Task(Room.objects.find, {},
                                       sort=[('visitors', 'ASC')])
        self.render_template('all_rooms.html', rooms=rooms)

class ChatHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render_template('personal_chat.html')

class RoomHandler(BaseHandler):

    @tornado.web.authenticated
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
        data['user'] = 'chater%i' % user.room_chater_id
        data['uuid'] = user.uuid
        c.publish(room, json.dumps(data))
        self.finish()

class LogoutHandler(BaseHandler):

    @tornado.web.asynchronous
    def get(self):
        self.clear_cookie('user')
        self.redirect('/')


class MessagesCatcher(BaseHandler, tornado.websocket.WebSocketHandler):

    @tornado.gen.engine
    def open(self):
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
        waiters = yield tornado.gen.Task(Waiters.objects.find_one, {})
        queue = waiters.queue[:]
        if user.chater:
            data = {}
            data['status'] = 'chat_ended'
            data['message'] = 'start'
            c.publish(user.chater, json.dumps(data))
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
        if user.uuid in queue:
            queue.remove(user.uuid)
        waiters.queue = queue
        yield tornado.gen.Task(waiters.update)
        if self.client.subscribed:
            self.client.unsubscribe(user.uuid)
            self.client.disconnect()

class RoomMessagesCatcher(BaseHandler, tornado.websocket.WebSocketHandler):

    @tornado.gen.engine
    def open(self, room_name):
        self.room_name = unicode(room_name, 'utf-8')
        room = yield tornado.gen.Task(Room.objects.find_one, {'name': self.room_name})
        user = yield tornado.gen.Task(self.user)
        if not room:
            room = Room()
            room.visitors = 1
            room.last_chater_id = 1
            room.name = self.room_name
            user.room_chater_id = room.last_chater_id
            user.last_room = room.name
            yield tornado.gen.Task(room.save)
        else:
            room.visitors += 1
            if user.last_room != room.name:
                room.last_chater_id += 1
                user.room_chater_id = room.last_chater_id
                user.last_room = room.name
            yield tornado.gen.Task(room.update)
        yield tornado.gen.Task(user.update)
        self.listen()

    @tornado.gen.engine
    def listen(self):
        self.client = tornadoredis.Client()
        user = yield tornado.gen.Task(self.user)
        room = yield tornado.gen.Task(Room.objects.find_one, {'name': self.room_name})
        if user:
            self.client.connect()
            yield tornado.gen.Task(self.client.subscribe, room.name)
            self.client.listen(self.on_message)

    def on_message(self, msg):
        if msg.kind == 'message':
            user_id = self.get_current_user()
            message = json.loads(msg.body)
            if user_id == message['uuid']:
                message['user'] = 'me'
            del message['uuid']
            self.write_message(message)
        if msg.kind == 'disconnect':
            # Do not forget to restart a listen loop
            # after a successful reconnect attempt.

            # Do not try to reconnect, just send a message back
            # to the client and close the client connection
            self.close()

    @tornado.gen.engine
    def on_close(self):
        room = yield tornado.gen.Task(Room.objects.find_one, {'name': self.room_name})
        room.visitors -= 1
        yield tornado.gen.Task(room.update)
        if self.client.subscribed:
            self.client.unsubscribe(room.name)
            self.client.disconnect()


application = tornado.web.Application([
    (r'/', MainHandler),
    (r'/login', LoginHandler),
    (r'/not_supported', NotSupportedHandler),
    (r'/chat', ChatHandler),
    (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': STATIC_PATH}),
    (r'/msg', NewMessage),
    (r'/room_msg/(.*)', RoomMessage),
    (r'/logout', LogoutHandler),
    (r'/ws/track', MessagesCatcher),
    (r'/popular_rooms', PopularRoomsHandler),
    (r'/all_rooms', AllRoomsHandler),
    (r'/ws/room_track/(.*)', RoomMessagesCatcher),
    (r'/room/(.*)', RoomHandler),
    (r'/change_chater', StartChatHandler),
], **settings)

if __name__ == '__main__':
    init_data()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    print 'Demo is runing at 0.0.0.0:8888\nQuit the demo with CONTROL-C'
    tornado.ioloop.IOLoop.instance().start()
