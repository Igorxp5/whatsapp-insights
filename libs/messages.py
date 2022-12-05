import os
import re
import uuid
import typing
import sqlite3

from enum import Enum
from datetime import datetime, tzinfo

from .contacts import ContactManager
from .type import Jid, FilePath, DirPath, MimeType
from .export_chats import parse_export_chat_file, EXPORT_CHAT_FILE_NAME

TMessage = typing.TypeVar('TMessage', bound='Message')


class Message:
    MIME_TYPE_AUDIO_REGEXP = re.compile(r'audio/.*')
    MIME_TYPE_VOICE_REGEXP = re.compile(r'audio/ogg; codecs=opus')
    MIME_TYPE_IMAGE_REGEXP = re.compile(r'image/.*')
    MIME_TYPE_VIDEO_REGEXP = re.compile(r'video/.*')

    def __init__(self, remote_jid: Jid, from_me: bool, key_id: str, status: int=None,
                 data: str=None, date: typing.Union[float, datetime]=None,
                 quote_message: TMessage=None, forwarded: bool=False,
                 mime_type: MimeType=None, media_duration: int=None,
                 media_name: str=None, tz: tzinfo=None):
        self.remote_jid: Jid = remote_jid
        self.from_me: bool = bool(from_me)
        self.key_id: str = key_id
        self.status: typing.Union[MessageStatus, int] = None
        try:
            self.status: MessageStatus = MessageStatus(status)
        except ValueError:
            self.status = status
        self.data: str = data
        self.date: datetime = datetime.fromtimestamp(date, tz=tz) if not isinstance(date, datetime) else date
        self.quote_message: Message = quote_message
        self.forwarded: bool = forwarded
        self.mime_type: MimeType = mime_type
        self.media_duration: int = media_duration
        self.media_name: str = media_name

    def __repr__(self):
        return f'{self.__class__.__name__}{(self.remote_jid, self.from_me, self.status, self.data, self.date, self.mime_type, self.media_duration)}'
    
    @staticmethod
    def is_audio(mime_type: MimeType) -> bool:
        return mime_type and bool(Message.MIME_TYPE_AUDIO_REGEXP.match(mime_type))
    
    @staticmethod
    def is_voice_message(mime_type: MimeType) -> bool:
        return mime_type and bool(Message.MIME_TYPE_VOICE_REGEXP.match(mime_type))

    @staticmethod
    def is_image(mime_type: MimeType) -> bool:
        return mime_type and bool(Message.MIME_TYPE_IMAGE_REGEXP.match(mime_type)) 
    
    @staticmethod
    def is_video(mime_type: MimeType) -> bool:
        return mime_type and bool(Message.MIME_TYPE_VIDEO_REGEXP.match(mime_type)) 


class MessageManager:
    def __init__(self):
        self._messages: typing.Dict[Jid, typing.List[Message]] = dict()
        self._contacts: typing.Set[Jid] = set()
    
    def __getitem__(self, jid: Jid):
        return self._messages[jid]
    
    def __iter__(self):
        return (message for messages in self._messages.values() for message in messages)
    
    @property
    def contacts(self) -> typing.Set[Jid]:
        return set(self._contacts)

    @staticmethod
    def from_msgstore_db(db_path: FilePath, tz: tzinfo=None) -> TMessage:
        sql = 'SELECT jid.raw_string, message.from_me, message.key_id, message.status, message.text_data, ' \
              'message.timestamp, message_media.mime_type, message_media.media_name, message_media.media_duration, ' \
              'message_forwarded.forward_score, ' \
              'NULL, message_quoted.from_me, message_quoted.key_id, NULL, message_quoted.text_data, message_quoted.timestamp, ' \
              'NULL, NULL, NULL, NULL, NULL, NULL ' \
              'FROM message INNER JOIN chat ON message.chat_row_id = chat._id ' \
              'INNER JOIN jid ON chat.jid_row_id = jid._id ' \
              'LEFT JOIN message_media ON message._id = message_media.message_row_id ' \
              'LEFT JOIN message_forwarded ON message._id = message_forwarded.message_row_id ' \
              'LEFT JOIN message_quoted ON message._id = message_quoted.message_row_id '
        with sqlite3.connect(db_path) as conn:
            message_manager = MessageManager()
            for row in conn.execute(sql):
                remote_jid = row[0]
                from_me = bool(row[1])
                key_id = row[2]
                status = row[3]
                data = row[4]
                timestamp = row[5] or 0
                mime_type = row[6]
                media_name = row[7]
                media_duration = row[8]
                forwarded = bool(row[9])
                message = Message(remote_jid, from_me, key_id, status, data, timestamp / 1000, 
                                  None, forwarded, mime_type, media_duration, media_name, tz=tz)
                
                if remote_jid not in message_manager._messages:
                    message_manager._contacts.add(remote_jid)
                    message_manager._messages[remote_jid] = []
                message_manager._messages[remote_jid].append(message)

                # quoted message
                quoted_key_id = row[12]
                if quoted_key_id:
                    remote_jid = row[10]
                    from_me = bool(row[11])
                    key_id = quoted_key_id
                    status = row[13]
                    data = row[14]
                    timestamp = row[15] or 0
                    mime_type = row[16]
                    media_name = row[17]
                    media_duration = row[18]
                    forwarded = row[19]
                    message.quote_message = Message(remote_jid, from_me, key_id, status, data, timestamp / 1000, 
                                                    None, forwarded, mime_type, media_duration, media_name, tz=tz)
                
        return message_manager
    
    def from_export_chats_folder(chats_folder: DirPath, contact_manager: ContactManager, tz: tzinfo=None) -> TMessage:
        message_manager = MessageManager()

        chat_files = [file for file in os.listdir(chats_folder) if EXPORT_CHAT_FILE_NAME.match(file)]
        for chat_file in chat_files:
            contact_name = EXPORT_CHAT_FILE_NAME.match(chat_file).group('contact_name')
            remote_jid = None
            chat_file = os.path.join(chats_folder, chat_file)

            messages = parse_export_chat_file(chat_file, tz)

            for message in messages:
                mime_type = '*/*' if message.media_message else None
                contact = contact_manager.get_contacts_by_display_name(message.contact_name)
                from_me = message.contact_name != contact_name
                if not from_me and not remote_jid:
                    remote_jid = contact[0].jid if contact else message.dummy_jid
                key_id = str(uuid.uuid4())
                status = MessageStatus.RECEIVED if from_me else MessageStatus.READ_BY_RECIPIENT
                message = Message(remote_jid, from_me, key_id, status, message.message, message.date, mime_type=mime_type)

                message_manager._messages.setdefault(remote_jid, [])
                message_manager._messages[remote_jid].append(message)

        return message_manager


class MessageStatus(Enum):
    RECEIVED = 0
    WAITING_ON_SERVER = 4
    RECEVED_AT_DESTINATION = 5
    CONTROL_MESSAGE = 6
    READ_BY_RECIPIENT = 13


if __name__ == '__main__':
    message_manager = MessageManager.from_msgstore_db('msgstore.db')