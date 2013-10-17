import tornado.gen
import tornado.websocket
import tornado.web
import json
import tornadoredis
from tornado.escape import json_encode
from base.handlers import BaseHandler
from base.redis_connection import c
from config import settings, MAX_HISTORY_MESSAGES
from .models import Room

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

class RoomHistoryHandler(BaseHandler):

    @tornado.gen.engine
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self, room_name):
        room = yield tornado.gen.Task(Room.objects.find_one, {'name': room_name})
        history = []
        if room and room.history:
            history = room.history[-MAX_HISTORY_MESSAGES:]
        self.set_header('Content-type', 'application/json')
        self.write(json_encode(history))
        self.finish()

class RoomMessage(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self, room):
        user = yield tornado.gen.Task(self.user)
        room = yield tornado.gen.Task(Room.objects.find_one, {'name': room})
        data = {}
        data['message'] = self.get_argument('message')
        data['status'] = 'message'
        data['user'] = 'chater%i' % user.room_chater_id
        data['uuid'] = user.uuid
        history = []
        if room.history:
            history = room.history[:]
        history.append(data)
        room.history = history
        yield tornado.gen.Task(room.update)
        c.publish(room.name, json.dumps(data))
        self.finish()

class RoomHandler(BaseHandler):

    @tornado.gen.engine
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self, room):
        yield tornado.gen.Task(self.user)
        self.render_template('room.html', room=room)

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

