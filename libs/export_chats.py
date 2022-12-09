import re
import typing
import datetime
import dataclasses

from .type import FilePath

EN_US_DATE_FORMAT = '%m/%d/%y %H:%M'
PT_BR_DATE_FORMAT = '%d/%m/%Y %H:%M'
EXPORT_CHAT_FILE_NAME = re.compile(r'(Conversa do WhatsApp com|WhatsApp Chat with) (?P<contact_name>.+).txt')
EXPORT_CHAT_MEDIA_MESSAGE = re.compile(r'<(Arquivo de mídia oculto|Media omitted)>')
CHAT_MESSAGE_PATTERN = re.compile(r'^\[?(?P<date>\d{1,2}\/\d{1,2}\/(?P<year>\d{2}|\d{4})),? (?P<time>\d{1,2}:\d{1,2})(?P<seconds>:\d{1,2})?\]? (?:- )?(?P<contact_name>.+?): (?P<message>.+)', re.MULTILINE)

@dataclasses.dataclass
class ExportChatMessage:
    message: str
    contact_name: str
    date: datetime.datetime
    dummy_jid: str = None
    media_message: bool = False


def parse_export_chat_file(filepath: FilePath, tz: datetime.tzinfo=None) -> typing.List[ExportChatMessage]:
    message_headers = []
    messages = []
    with open(filepath, encoding='utf-8') as file:
        messages_raw = file.read()

    for match in CHAT_MESSAGE_PATTERN.finditer(messages_raw):
        message_headers.append(match)

    for i, header in enumerate(message_headers):
        date_format = PT_BR_DATE_FORMAT if len(header.group('year')) == 4 else EN_US_DATE_FORMAT
        date = f'{header.group("date")} {header.group("time")}'
        date = datetime.datetime.strptime(date, date_format)
        if tz:
            date = date.replace(tzinfo=tz)
        contact_name = header.group('contact_name').strip()
        start_index = header.start('message')
        end_index = message_headers[i + 1].start() if i + 1 < len(message_headers) else len(messages_raw) 
        message_data = messages_raw[start_index:end_index].strip()
        media_message = bool(EXPORT_CHAT_MEDIA_MESSAGE.match(message_data))
        dummy_jid = re.sub(r'[. ]', '_', contact_name).lower() + '@s.whatsapp.net'
        message = ExportChatMessage(message_data, contact_name, date, dummy_jid, media_message)
        
        messages.append(message)

    return messages
