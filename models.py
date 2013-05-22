from mongotor.orm.collection import Collection
from mongotor.orm.field import StringField, ObjectIdField, ListField,\
    IntegerField

class User(Collection):

    __collection__ = 'users'
    _id = ObjectIdField()
    uuid = StringField()
    chater = StringField()

class Room(Collection):

    __collection__ = 'rooms'
    _id = ObjectIdField()
    name = StringField()
    visitors = IntegerField()


class Waiters(Collection):

    __collection__ = 'queue'
    _id = ObjectIdField()
    queue = ListField()
    er = StringField()
