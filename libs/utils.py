import io
import os
import re
import zlib
import locale
import base64
import typing
import subprocess
import contextlib

from PIL import Image
from Crypto.Cipher import AES
from difflib import SequenceMatcher

from .messages import Message
from .type import FilePath, Jid
from .contacts import ContactManager


def get_adb_serials(include_emulators: bool=True) -> typing.List[str]:
    out = subprocess.check_output(['adb', 'devices'], shell=True, text=True).strip('\r\n').strip('\n')
    devices = [d for d in re.findall(r'(\S+)\tdevice', out) if include_emulators or not d.startswith('emulator-')]
    return devices


def time_delta_to_str(time: str, units: typing.List[str], round_=False) -> str:
    factors = {'d': 3600 * 24, 'h': 3600, 'm': 60, 's': 1}
    
    if round_:
        last_suffix_factor = factors[units[-1]]
        time += last_suffix_factor - time % last_suffix_factor
    
    result = []
    for unit in units:
        factor = factors[unit]
        value = int(time / factor)
        time = time % factor
        if value > 0:
            result.append(f'{value}{unit}')
    
    return ' '.join(result)

def pillow_image_to_base64(image: Image, format_: str):
    buffer = io.BytesIO()
    image.save(buffer, format_)
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def decrypt_whatsapp_database(db_file: FilePath, key_file: FilePath, output: FilePath):
    # Credits to https://github.com/B16f00t/whapa/blob/master/libs/whacipher.py

    if os.path.getsize(key_file) != 158:
        raise RuntimeError('Invalid key')

    with open(key_file, 'rb') as file:
        key_data = file.read()

    key = key_data[126:]
    with open(db_file, 'rb') as file:
        db_data = file.read()
    
    _, db_extension = os.path.splitext(db_file)

    if db_extension == '.crypt14':
        data = db_data[191:]
        iv = db_data[67:83]
    elif db_extension == '.crypt12':
        data = db_data[67:-20]
        iv = db_data[51:67]
    else:
        raise OSError('DB encrypt not supported')
    
    aes = AES.new(key, mode=AES.MODE_GCM, nonce=iv)
    with open(output, 'wb') as file:
        file.write(zlib.decompress(aes.decrypt(data)))


def string_similarity(string: str, string2: str) -> float:
    return SequenceMatcher(None, string, string2).ratio()


@contextlib.contextmanager
def context_locale(locale_: str):
    default_locale = f'{locale.getdefaultlocale()[0]}.UTF-8'
    locale.setlocale(locale.LC_ALL, locale_)
    try:
        yield
    finally:
        locale.setlocale(locale.LC_ALL, default_locale)


def group_messages_by_contact_name(contact_manager: ContactManager,
                                   sorted_messages: typing.Iterable[Message]) -> typing.List[Message]:
    messages = list(sorted_messages)
    contact_name_most_recent = dict()
    for message in messages:
        contact = contact_manager.get(message.remote_jid)
        if contact.display_name:
            for c in contact_manager.get_contacts_by_display_name(contact.display_name):
                contact_name_most_recent[c.jid] = contact
    
    for message in messages:
        if message.remote_jid in contact_name_most_recent:
            message.remote_jid = contact_name_most_recent[message.remote_jid].jid
    
    return messages


def get_profile_image_filename_by_jid(jid: Jid):
    return f'{jid}.jpg'
