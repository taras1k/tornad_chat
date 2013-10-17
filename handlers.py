import tornado.web
import tornado.gen
from users.models import User

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

    def get_current_user(self):
        return self.get_secure_cookie('user')

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
            self.redirect(self.get_argument('next', '/chat'))
        else:
            self.render_template('index.html', title='Chat')
