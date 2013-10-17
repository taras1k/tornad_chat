from mongotor.orm.collection import Collection
from mongotor.orm.field import StringField, ObjectIdField, ListField,\
    IntegerField


class Room(Collection):

    __collection__ = 'rooms'
    _id = ObjectIdField()
    name = StringField()
    visitors = IntegerField()
    last_chater_id = IntegerField()
    history = ListField()
