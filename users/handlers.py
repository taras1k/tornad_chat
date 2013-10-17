import tornado.gen
import tornado.websocket
import tornado.web
import uuid
import tornadoredis
import random
from base.handlers import BaseHandler
from base.redis_connection import c
from recaptcha import RecaptchaClient, RecaptchaUnreachableError, RecaptchaException
from config import settings
from .models import User, Waiters

class StartChatHandler(BaseHandler):

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
            user.chater = next_chater
        if next_chater and next_chater != user.uuid:
            data['status'] = 'chat_started'
            data['message'] = 'start'
            c.publish(next_chater, json.dumps(data))
            c.publish(user.uuid, json.dumps(data))
            user.chater = next_chater
            queue.remove(next_chater)
            if user.uuid in queue:
                queue.remove(user.uuid)
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
        yield tornado.gen.Task(user.update)
        yield tornado.gen.Task(waiters.update)

    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self):
        self.change_chater()
        self.finish()

class ChatHandler(BaseHandler):

    @tornado.gen.engine
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self):
        yield tornado.gen.Task(self.user)
        self.render_template('personal_chat.html')


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
