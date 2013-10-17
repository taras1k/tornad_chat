# -*- coding: utf-8 -*-
import logging
import tornado.httpserver
import tornado.auth
import tornado.web
import tornado.ioloop
import tornado.options
from mongotor.database import Database
from config import STATIC_PATH, settings
from handlers import MainHandler, NotSupportedHandler
from users.handlers import LogoutHandler, LoginHandler, ChatHandler,\
    NewMessage, StartChatHandler, MessagesCatcher
from room_chat.handlers import RoomMessage, PopularRoomsHandler,\
    AllRoomsHandler, RoomMessagesCatcher, RoomHandler, RoomHistoryHandler

tornado.options.parse_command_line()

Database.connect(['localhost:27017'], 'anon_chat')

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
    (r'/room_history/(.*)', RoomHistoryHandler),
    (r'/change_chater', StartChatHandler),
], **settings)

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    print 'Demo is runing at 0.0.0.0:8888\nQuit the demo with CONTROL-C'
    tornado.ioloop.IOLoop.instance().start()
