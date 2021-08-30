import re
import os
import logging
import argparse
import tempfile
import subprocess

from libs import automation, utils
from libs.android import Android
from libs.contacts import JID_REGEXP, ContactManager
from libs.insighters import InsighterManager, LongestAudioInsighter, \
    GreatestAudioAmountInsighter, GreatestAmountOfDaysTalkingInsighter, \
    LongestConversationInsighter, TopMessagesAmountInsighter, \
    GreatestPhotoAmountInsighter, LongestCallInsighter, \
    GreatestCallAmountInsighter, LongestTimeInCallsInsighter

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
                              default=['TopMessagesAmountInsighter', 'LongestAudioInsighter', 'GreatestAudioAmountInsighter', 
                                       'GreatestAmountOfDaysTalkingInsighter', 'GreatestPhotoAmountInsighter', 'LongestConversationInsighter', 
                                       'LongestCallInsighter', 'GreatestCallAmountInsighter', 'LongestTimeInCallsInsighter'], 
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
