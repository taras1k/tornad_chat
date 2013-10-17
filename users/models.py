from mongotor.orm.collection import Collection
from mongotor.orm.field import StringField, ObjectIdField, ListField,\
    IntegerField

class User(Collection):

    __collection__ = 'users'
    _id = ObjectIdField()
    uuid = StringField()
    chater = StringField()
    room_chater_id = IntegerField()
    last_room = StringField()


class Waiters(Collection):

    __collection__ = 'queue'
    _id = ObjectIdField()
    queue = ListField()
