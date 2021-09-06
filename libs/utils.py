import io
import os
import zlib
import locale
import base64
import contextlib

from Crypto.Cipher import AES
from difflib import SequenceMatcher


def time_delta_to_str(time, units, round_=False):
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

def pillow_image_to_base64(image, format):
    buffer = io.BytesIO()
    image.save(buffer, format)
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def decrypt_whatsapp_database(db_file, key_file, output):
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


def stringy_similarity(string, string2):
    return SequenceMatcher(None, string, string2).ratio()


@contextlib.contextmanager
def context_locale(locale_):
    default_locale = f'{locale.getdefaultlocale()[0]}.UTF-8'
    locale.setlocale(locale.LC_ALL, locale_)
    try:
        yield
    finally:
        locale.setlocale(locale.LC_ALL, default_locale)
