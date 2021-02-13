import re
import sqlite3

from enum import Enum
from datetime import datetime

class MessageManager:
    def __init__(self):
        self._messages = {}
        self._contacts = set()
    
    def __getitem__(self, jid):
        return self._messages[jid]
    
    def __iter__(self):
        return (message for messages in self._messages.values() for message in messages)
    
    @property
    def contacts(self):
        return set(self._contacts)

    @staticmethod
    def from_msgstore_db(db_path, tz=None):
        with sqlite3.connect(db_path) as conn:
            message_manager = MessageManager()
            for row in conn.execute('SELECT * FROM messages'):
                remote_jid = row[1]
                from_me = bool(row[2])
                status = row[4]
                data = row[6]
                timestamp = row[7]
                mime_type = row[9]
                media_name = row[12]
                media_duration = row[15]
                forwarded = row[37]
                message = Message(remote_jid, from_me, status, data, timestamp / 1000, 
                                  forwarded, mime_type, media_duration, media_name, tz=tz)
                if remote_jid not in message_manager._messages:
                    message_manager._contacts.add(remote_jid)
                    message_manager._messages[remote_jid] = []
                message_manager._messages[remote_jid].append(message)
        return message_manager


class MessageStatus(Enum):
    RECEIVED = 0
    WAITING_ON_SERVER = 4
    RECEVED_AT_DESTINATION = 5
    CONTROL_MESSAGE = 6
    READ_BY_RECIPIENT = 13


class Message:
    MIME_TYPE_AUDIO_REGEXP = re.compile(r'audio/.*')
    MIME_TYPE_VOICE_REGEXP = re.compile(r'audio/ogg; codecs=opus')
    MIME_TYPE_IMAGE_REGEXP = re.compile(r'image/.*')
    MIME_TYPE_VIDEO_REGEXP = re.compile(r'video/.*')

    def __init__(self, remote_jid, from_me, status=None, data=None, timestamp=None, 
                 forwarded=False, mime_type=None, media_duration=None, media_name=None, tz=None):
        self.remote_jid = remote_jid
        self.from_me = from_me
        try:
            self.status = status and MessageStatus(status)
        except ValueError:
            self.status = status
        self.data = data
        self.timestamp = datetime.fromtimestamp(timestamp, tz=tz) if not isinstance(timestamp, datetime) else timestamp
        self.forwarded = forwarded
        self.mime_type = mime_type
        self.media_duration = media_duration
        self.media_name = media_name
    
    def __repr__(self):
        return f'{self.__class__.__name__}{(self.remote_jid, self.from_me, self.status, self.data, self.timestamp, self.mime_type, self.media_duration)}'
    
    @staticmethod
    def is_audio(mime_type):
        return mime_type and bool(Message.MIME_TYPE_AUDIO_REGEXP.match(mime_type))
    
    @staticmethod
    def is_voice_message(mime_type):
        return mime_type and bool(Message.MIME_TYPE_VOICE_REGEXP.match(mime_type))

    @staticmethod
    def is_image(mime_type):
        return mime_type and bool(Message.MIME_TYPE_IMAGE_REGEXP.match(mime_type)) 
    
    @staticmethod
    def is_video(mime_type):
        return mime_type and bool(Message.MIME_TYPE_VIDEO_REGEXP.match(mime_type)) 

if __name__ == '__main__':
    message_manager = MessageManager.from_msgstore_db('msgstore.db')