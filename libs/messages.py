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
        sql = 'SELECT * FROM messages LEFT JOIN messages_quotes ON messages.quoted_row_id=messages_quotes._id'
        with sqlite3.connect(db_path) as conn:
            message_manager = MessageManager()
            for row in conn.execute(sql):
                remote_jid = row[1]
                from_me = bool(row[2])
                key_id = row[3]
                status = row[4]
                data = row[6]
                timestamp = row[7] or 0
                mime_type = row[9]
                media_name = row[12]
                media_duration = row[15]
                forwarded = row[37]
                message = Message(remote_jid, from_me, key_id, status, data, timestamp / 1000, 
                                  None, forwarded, mime_type, media_duration, media_name, tz=tz)
                
                if remote_jid not in message_manager._messages:
                    message_manager._contacts.add(remote_jid)
                    message_manager._messages[remote_jid] = []
                message_manager._messages[remote_jid].append(message)

                # quoted message
                if row[31]:
                    remote_jid = row[42+1]
                    from_me = bool(row[42+2])
                    key_id = row[42+3]
                    status = row[42+4]
                    data = row[42+6]
                    timestamp = row[42+7] or 0
                    mime_type = row[42+9]
                    media_name = row[42+12]
                    media_duration = row[42+15]
                    forwarded = row[42+37]
                    message.quote_message = Message(remote_jid, from_me, key_id, status, data, timestamp / 1000, 
                                                    None, forwarded, mime_type, media_duration, media_name, tz=tz)
                
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

    def __init__(self, remote_jid, from_me, key_id, status=None, data=None, date=None,
                 quote_message=None, forwarded=False, mime_type=None, media_duration=None, media_name=None, tz=None):
        self.remote_jid = remote_jid
        self.from_me = bool(from_me)
        self.key_id = key_id
        try:
            self.status = status and MessageStatus(status)
        except ValueError:
            self.status = status
        self.data = data
        self.date = datetime.fromtimestamp(date, tz=tz) if not isinstance(date, datetime) else date
        self.quote_message = quote_message
        self.forwarded = forwarded
        self.mime_type = mime_type
        self.media_duration = media_duration
        self.media_name = media_name
    
    def __repr__(self):
        return f'{self.__class__.__name__}{(self.remote_jid, self.from_me, self.status, self.data, self.date, self.mime_type, self.media_duration)}'
    
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