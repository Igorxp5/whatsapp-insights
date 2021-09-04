import io
import re
import os
import json
import base64
import logging
import argparse
import tempfile
import subprocess

from PIL import Image

from libs import automation, utils
from libs import insighters_image
from libs.android import Android
from libs.calls import CallManager
from libs.messages import MessageManager
from libs.contacts import JID_REGEXP, ContactManager
from libs.insighters import InsighterManager, LongestAudioInsighter, \
    GreatestAudioAmountInsighter, GreatestAmountOfDaysTalkingInsighter, \
    LongestConversationInsighter, TopMessagesAmountInsighter, \
    GreatestPhotoAmountInsighter, LongestCallInsighter, \
    GreatestCallAmountInsighter, LongestTimeInCallsInsighter

from libs.chart_race import create_chart_race_video
from libs.insighters_image import create_insights_image

ANDROID_HOME = os.environ.get('ANDROID_HOME')
SDK_MANAGER = os.environ.get('SDK_MANAGER')

INSIGHTERS = {
    'LongestAudioInsighter': LongestAudioInsighter,
    'GreatestAudioAmountInsighter': GreatestAudioAmountInsighter,
    'GreatestAmountOfDaysTalkingInsighter': GreatestAmountOfDaysTalkingInsighter,
    'GreatestPhotoAmountInsighter': GreatestPhotoAmountInsighter,
    'TopMessagesAmountInsighter': TopMessagesAmountInsighter,
    'LongestConversationInsighter': LongestConversationInsighter,
    'LongestCallInsighter': LongestCallInsighter,
    'GreatestCallAmountInsighter': GreatestCallAmountInsighter,
    'LongestTimeInCallsInsighter': LongestTimeInCallsInsighter,
}

DEFAULT_PROFILE_IMAGE = os.path.join(os.path.dirname(__file__), 'images', 'profile-image.png')
LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locale')


def get_adb_serials(include_emulators=True):
    out = subprocess.check_output(['adb', 'devices'], shell=True, text=True).strip('\r\n').strip('\n')
    devices = [d for d in re.findall(r'(\S+)\tdevice', out) if include_emulators or not d.startswith('emulator-')]
    return devices


def extract_contacts(msg_store, serial, profile_pictures_dir, output):
    if not serial:
        logging.error('No device serial provided')
        return
    
    if serial not in get_adb_serials():
        logging.error(f'Device "{serial}" not found')
        return
    
    if not msg_store or not os.path.exists(msg_store):
        logging.error(f'Messages database not found in path "{msg_store}"')
        return
    
    if not profile_pictures_dir:
        logging.error('No profile_pictures_dir provided')
        return
    
    if not output:
        logging.error('No output file provided')
        return
    
    os.makedirs(profile_pictures_dir, exist_ok=True)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    
    android = Android(serial)

    logging.warning('Before starting make sure your device is unlocked!')
    input('Press Enter to continue...')

    automation.force_stop_whatsapp(android)
    contacts = automation.get_main_screen_contacts_info(android, include_groups=False)
    contact_manager = ContactManager()

    for phone_number, (display_name, photo, is_group) in contacts.items():
        logging.info(f'Adding "{display_name}" to Contact Manager')
        jid = re.sub(r'[\+\s-\(\)]', '', phone_number) + '@s.whatsapp.net'
        contact = contact_manager.add_contact(jid, display_name)
        if photo:
            contact.profile_image = utils.pillow_image_to_base64(photo, format='PNG') 
            profile_picture_path = os.path.join(profile_pictures_dir, jid)
            logging.info(f'Saving "{display_name}" profile picture at "{profile_picture_path}"')
            photo.save(profile_picture_path, format='PNG')

    contact_manager.export_vcf(output, include_groups=False)

def extract_database(backup, serial, key, output):
    if not serial:
        logging.error('No device serial provided')
        return
    
    if serial not in get_adb_serials():
        logging.error(f'Device "{serial}" not found')
        return
    
    if not key:
        logging.error('No key file provided')
        return
    
    if not output:
        logging.error('No output file provided')
        return
    
    android = Android(serial)

    if backup:
        logging.warning('Before starting make sure your device is unlocked!')
        input('Press Enter to continue...')
        logging.info('Opening WhatsApp to backup the messages...')
        try:
            logging.info(f'Turning off Wi-fi...')
            automation.set_wifi_state(android, False)
            logging.info(f'Backuping WhatsApp messages...')
            automation.backup_whatsapp_messages(android)
            logging.info(f'Backup finished!')
        finally:
            logging.info(f'Turning on Wi-fi...')
            automation.force_stop_whatsapp(android)
            automation.set_wifi_state(android, True)
    
    logging.info(f'Pulling WhatsApp backup from the device...')
    with tempfile.TemporaryDirectory() as temp_dir:
        enc_db_path = os.path.join(temp_dir, 'msgstore.db.crypt14')
        try:
            android.pull('/sdcard/WhatsApp/Databases/msgstore.db.crypt14', enc_db_path)
        except FileNotFoundError:
            enc_db_path = os.path.join(temp_dir, 'msgstore.db.crypt12')
            try:
                android.pull('/sdcard/WhatsApp/Databases/msgstore.db.crypt12', enc_db_path)
            except FileNotFoundError:
                logging.error('WhatsApp database backup not found in "/sdcard/WhatsApp/Databases/"')
                return
        logging.info(f'Decrypting database backup...')
        utils.decrypy_whatsapp_database(enc_db_path, key, output)    
        logging.info(f'Database extracted!')


def generate_image(msg_store, locale, profile_pictures_dir, contacts, insighters, output):
    try:
        insighters_classes = [INSIGHTERS[i] for i in insighters]
    except KeyError as error:
        logging.error(f'Invalid insighter "{error.args[0]}"')
        return
    
    if not msg_store or not os.path.exists(msg_store):
        logging.error(f'Messages database not found in path "{msg_store}"')
        return
    
    if not output:
        logging.error('No output file provided')
        return
    
    locale_strings = dict()
    if locale:
        locale_path = os.path.join(LOCALE_DIR, f'{locale}.json')
        if not os.path.exists(locale_path):
            logging.error(f'Could not find locale file for "{locale}"')
            return
        else:
            logging.info(f'Loading locale file "{locale}"...')
            with open(locale_path, encoding='utf-8') as file:
                locale_strings = json.load(file)
    
    logging.info('Loading contacts...')
    vcf_contact_manager = ContactManager.from_vcf(contacts)
    contact_manager = ContactManager.from_msgtore_db(msg_store)
    
    logging.info('Getting contact and profile pictures from vcf...')
    for contact in contact_manager.get_users():
        for vcf_contact in vcf_contact_manager.get_users():
            if utils.stringy_similarity(vcf_contact.jid, contact.jid) >= 0.95:
                if not contact.display_name:
                    contact.display_name = vcf_contact.display_name
                contact.profile_image = vcf_contact.profile_image
                break

    logging.info('Identifying profile pictures in the directory provided...')
    profile_pictures = dict()
    if profile_pictures_dir:
        for filename in os.listdir(profile_pictures_dir):
            match = JID_REGEXP.search(filename)
            if match:
                with open(os.path.join(profile_pictures_dir, filename), 'rb') as file:
                    profile_pictures[match.group(0)] = base64.b64encode(file.read()).decode('ascii')
    
    insighter_manager = InsighterManager(contact_manager=contact_manager, group_by_name=True)

    for insighter in insighters_classes:
        insighter_strings = locale_strings.get(insighter.__name__, {})
        title = insighter_strings.get('title')
        format_ = insighter_strings.get('format')
        insighter_manager.add_insighter(insighter(title=title, format_=format_))

    logging.info('Loading call logs...')
    call_manager = CallManager.from_msgstore_db(msg_store)
    
    logging.info('Loading messages...')
    message_manager = MessageManager.from_msgstore_db(msg_store)

    logging.info('Applying messages in the insighters...')
    for message in message_manager:
        insighter_manager.update(message)

    logging.info('Applying calls in the insighters...')
    for call in call_manager:
        insighter_manager.update(call)

    logging.info('Result')
    logging.info('')
    for insighter in insighter_manager.insighters:
        logging.info(f'{insighter.title}')
        winners = insighter.winner
        if not isinstance(insighter.winner, list):
            winners = [insighter.winner]
        for winner in winners:
            logging.info(f'{contact_manager.get(winner.jid).display_name}: {winner.value}')
            if winner.data:
                logging.info(f'{repr(winner.data)}')
        logging.info('')


    logging.info('Grouping contacts and profile pictures data...')
    image_contacts = dict()
    for contact in contact_manager.get_users():
        profile_picture = profile_pictures.get(contact.jid, contact.profile_image)
        if profile_picture:
            profile_picture = Image.open(io.BytesIO(base64.b64decode(profile_picture)))
        image_contacts[contact.jid] = contact.display_name, profile_picture
    
    logging.info('Generating the image...')
    create_insights_image(insighter_manager.insighters, '8163093.jpg', image_contacts, output_path=output)


def generate_video(msg_store, locale, profile_pictures_dir, contacts, output, group_contact_by_name=True):
    if not msg_store or not os.path.exists(msg_store):
        logging.error(f'Messages database not found in path "{msg_store}"')
        return
    
    if not output:
        logging.error('No output file provided')
        return
    
    logging.info('Loading contacts...')
    vcf_contact_manager = ContactManager.from_vcf(contacts)
    contact_manager = ContactManager.from_msgtore_db(msg_store)
    
    logging.info('Getting contact and profile pictures from vcf...')
    for contact in contact_manager.get_users():
        for vcf_contact in vcf_contact_manager.get_users():
            if utils.stringy_similarity(vcf_contact.jid, contact.jid) >= 0.95:
                if not contact.display_name:
                    contact_manager.update_contact_diplay_name(contact.jid, vcf_contact.display_name)
                contact.profile_image = vcf_contact.profile_image
                break

    logging.info('Identifying profile pictures in the directory provided...')
    if profile_pictures_dir:
        for filename in os.listdir(profile_pictures_dir):
            match = JID_REGEXP.search(filename)
            if match:
                contact = contact_manager.get(match.group(0))
                if contact:
                    with open(os.path.join(profile_pictures_dir, filename), 'rb') as file:
                        contact.profile_image = base64.b64encode(file.read()).decode('ascii')
    
    logging.info('Loading messages...')
    message_manager = MessageManager.from_msgstore_db(msg_store)
    create_chart_race_video(contact_manager, message_manager, output, locale, group_contact_by_name=group_contact_by_name)


if __name__ == '__main__':
    default_device_serial = next(iter(get_adb_serials(include_emulators=False)), None)

    parser = argparse.ArgumentParser(description='Collect insights from WhatsApp',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', description='commands')
    subparsers.required = True

    key_parser = subparsers.add_parser('extract-key', help='Extract WhatsApp database key',
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    key_parser.add_argument('--no-verify-apk', action='store_true', default=False, dest='verify_apk', 
                            help='Verify WhatsApp APK signature before install in the emulator')
    key_parser.add_argument('--no-backup', action='store_false', default=True, dest='backup', 
                            help='Do not backup WhatsApp messages before extracting the key (Not recommended).')
    key_parser.add_argument('--show-emulator', action='store_true', default=False, dest='show_emulator',
                            help='Show emulator window while the key extraction is happening')
    key_parser.add_argument('--serial', dest='serial', help='Serial device for backup WhatsApp messages')
    key_parser.add_argument('--whatsapp-apk-file', dest='whatsapp_apk_file', 
                            help='WhatsApp APK to install in the emulator. By default the APK is installed from APKMirror')
    key_parser.add_argument('--output', dest='output', default='./key', help='Key output file path')
    
    database_parser = subparsers.add_parser('extract-database', help='Extract WhatsApp database',
                                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    database_parser.add_argument('--no-backup', action='store_false', default=True, dest='backup', 
                                 help='Do not backup WhatsApp messages. Use the last backup created.')
    database_parser.add_argument('--serial', dest='serial', default=default_device_serial, 
                                 help='Serial device for backup WhatsApp messages')
    database_parser.add_argument('--key', dest='key', default='./key', help='WhatsApp encrypt key file path')
    database_parser.add_argument('--output', dest='output', default='./msgstore.db', help='Messages database output file path')
    
    contacts_parser = subparsers.add_parser('extract-contacts', help='Extract WhatsApp contacts',
                                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    contacts_parser.add_argument('--msg-store', dest='msg_store', default='msgstore.db', help='WhatsApp database file path')
    contacts_parser.add_argument('--serial', dest='serial', default=default_device_serial,
                                 help='Serial device for pull the contacts')
    contacts_parser.add_argument('--profile-pictures-dir', dest='profile_pictures_dir', default='./profile_pictures',
                                 help='Directory for pull the contact profile pictures. If the directory does not exist, it will be created')
    contacts_parser.add_argument('--output', dest='output', default='./contacts.vcf', help='VCF contacts output file path')
    
    image_parser = subparsers.add_parser('generate-image', help='Generate Insights image',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    image_parser.add_argument('--msg-store', dest='msg_store', default='msgstore.db', help='WhatsApp database file path')
    image_parser.add_argument('--locale', dest='locale', default='en_US', help='Output language texts')
    image_parser.add_argument('--profile-pictures-dir', dest='profile_pictures_dir', default='./profile_pictures',
                              help='Directory to look for contact profile pictures. ' 
                                   'It will be used default profile picture when the program do not find')
    image_parser.add_argument('--contacts', dest='contacts', default='./contacts.vcf', help='Contacts export file path')
    image_parser.add_argument('--insighters', nargs='+', dest='insighters', choices=list(INSIGHTERS.keys()),
                              default=['TopMessagesAmountInsighter', 'LongestConversationInsighter', 'LongestAudioInsighter',
                                        'GreatestAudioAmountInsighter', 'GreatestPhotoAmountInsighter', 
                                        'GreatestAmountOfDaysTalkingInsighter', 'LongestTimeInCallsInsighter'], 
                              help='Contacts export file path')
    image_parser.add_argument('--output', dest='output', default='./insights.png', help='Insights output image file')

    video_parser = subparsers.add_parser('generate-video', help='Generate Chart Race video',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    video_parser.add_argument('--msg-store', dest='msg_store', default='msgstore.db', help='WhatsApp database file path')
    video_parser.add_argument('--locale', dest='locale', default='en_US', help='Output language texts')
    video_parser.add_argument('--profile-pictures-dir', dest='profile_pictures_dir', default='./profile_pictures',
                              help='Directory to look for contact profile pictures. ' 
                                   'It will be used default profile picture when the program do not find')
    video_parser.add_argument('--contacts', dest='contacts', default='./contacts.vcf', help='Contacts export file path')
    video_parser.add_argument('--output', dest='output', default='./chat-race.mp4', help='Chart Race output video file')

    rank_parser = subparsers.add_parser('generate-rank-file', help='Generate JSON file containing the rank of each ',
                                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    rank_parser.add_argument('--msg-store', dest='msg_store', default='msgstore.db', help='WhatsApp database file path')
    rank_parser.add_argument('--locale', dest='locale', default='en_US', help='Output language texts')
    rank_parser.add_argument('--profile-pictures-dir', dest='profile_pictures_dir', default='./profile_pictures',
                              help='Directory to look for contact profile pictures. ' 
                                   'It will be used default profile picture when the program do not find')
    rank_parser.add_argument('--contacts', dest='contacts', default='./contacts.vcf', help='Contacts export file path')
    rank_parser.add_argument('--output', dest='output', default='./rank.json', help='Rank output JSON file')

    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

    kwargs = vars(args)
    globals()[kwargs.pop('command').replace('-', '_')](**kwargs)
