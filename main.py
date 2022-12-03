import io
import os
import json
import base64
import logging
import argparse
import tempfile
import requests

from PIL import Image

from libs import automation, utils
from libs.android import Android
from libs.calls import CallManager
from libs.sdk_manager import SDKManager
from libs.messages import MessageManager
from libs.android_emulator import AndroidEmulator
from libs.contacts import JID_REGEXP, ContactManager
from libs.insighters import InsighterManager, LongestAudioInsighter, \
    GreatestAudioAmountInsighter, GreatestAmountOfDaysTalkingInsighter, \
    LongestConversationInsighter, GreatestMessagesAmountInsighter, \
    GreatestMyStatusAnsweredInsighter, GreatestPhotoAmountInsighter, \
    LongestCallInsighter, GreatestCallAmountInsighter, LongestTimeInCallsInsighter

from libs.whatsapp_web import WhatsAppWeb
from libs.chart_race import create_chart_race_video
from libs.insighters_image import create_insights_image

ANDROID_HOME = os.environ.get('ANDROID_HOME')
SDK_MANAGER = os.environ.get('SDK_MANAGER')

INSIGHTERS = {
    'LongestAudioInsighter': LongestAudioInsighter,
    'GreatestAudioAmountInsighter': GreatestAudioAmountInsighter,
    'GreatestAmountOfDaysTalkingInsighter': GreatestAmountOfDaysTalkingInsighter,
    'GreatestPhotoAmountInsighter': GreatestPhotoAmountInsighter,
    'GreatestMessagesAmountInsighter': GreatestMessagesAmountInsighter,
    'LongestConversationInsighter': LongestConversationInsighter,
    'GreatestMyStatusAnsweredInsighter': GreatestMyStatusAnsweredInsighter,
    'LongestCallInsighter': LongestCallInsighter,
    'GreatestCallAmountInsighter': GreatestCallAmountInsighter,
    'LongestTimeInCallsInsighter': LongestTimeInCallsInsighter,
}

DEFAULT_PROFILE_IMAGE = os.path.join(os.path.dirname(__file__), 'images', 'profile-image.png')
LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locale')

RANK_DATE_FORMAT = '%d %b %Y %H:%M:%S'
CHROMEDRIVER_BIN = 'chromedriver.exe' if os.name == 'nt' else 'chromedriver'

# WhatsApp Messenger 2.21.16.20 (x86_64) (Android 4.1+)
WHATSAPP_APK_URL = 'https://www.apkmirror.com/wp-content/themes/APKMirror/download.php?id=2554798'
WHATSAPP_FINGERPRINT_SHA256 = '3987d043d10aefaf5a8710b3671418fe57e0e19b653c9df82558feb5ffce5d44'

AVD_NAME = 'whatsapp-insights'
BUILD_TOOLS_PACKAGE = 'system-images;android-29;google_apis;x86_64'


def extract_key(serial, verify_apk, backup, show_emulator, whatsapp_apk_file, output):
    if backup and not serial:
        logging.error('To backup WhatsApp messages provide device serial')
        return

    if backup and serial not in utils.get_adb_serials():
        logging.error(f'Device "{serial}" not found')
        return

    if backup:
        android = Android(serial)
        logging.warning('Before starting make sure your device is unlocked!')
        input('Press Enter to continue...')
        logging.info('Opening WhatsApp to backup the messages...')
        logging.info(f'Turning off Wi-fi...')
        automation.set_wifi_state(android, False)
        logging.info(f'Backuping WhatsApp messages...')
        automation.backup_whatsapp_messages(android)
        logging.info(f'Backup finished!')
    
    sdk_manager = SDKManager(android_home=ANDROID_HOME, sdk_manager=SDK_MANAGER)
    if not sdk_manager.is_package_installed(BUILD_TOOLS_PACKAGE):
        sdk_manager.install_package(BUILD_TOOLS_PACKAGE)

    if AVD_NAME not in AndroidEmulator.available_avd():
        AndroidEmulator.create_avd(AVD_NAME, 'Nexus 5', BUILD_TOOLS_PACKAGE)
    
    emulator = AndroidEmulator(AVD_NAME, show_window=show_emulator)
    logging.info('Waiting emulator to start...')
    emulator.wait_boot()
    logging.info('Device emulator is ready!')

    emulator = emulator.adb
    
    logging.info('Putting emulator in root state')
    emulator.root()

    logging.info('Checking if WhatsApp is installed...')
    if not emulator.is_app_installed(automation.WHTASAPP_PACKAGE):
        if not whatsapp_apk_file:
            whatsapp_apk = os.path.join('whatsapp.apk')
            try:
                logging.info('Downloading WhatsApp APK...')
                response = requests.get(WHATSAPP_APK_URL, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.84'})

                assert response.status_code == 200
                
                with open(whatsapp_apk, 'wb') as file:
                    file.write(response.content)
                
            except Exception as error:
                raise RuntimeError('failed to download WhatsApp APK', error)

            logging.info('WhatsApp APK downloaded!')

            if not verify_apk:
                logging.warning('WhatsApp APK signature will not be checked!')

            automation.install_apk(emulator, whatsapp_apk, verify_apk and sdk_manager, 
                                    verify_apk and WHATSAPP_FINGERPRINT_SHA256)
        else:
            automation.install_apk(emulator, whatsapp_apk_file)
        
        if not emulator.is_app_installed(automation.WHTASAPP_PACKAGE):
            logging.error('Failed to install WhatsApp')
            return

    automation.extract_whatsapp_key(emulator, output)

    if backup:
        logging.info(f'Turning on Wi-fi...')
        automation.force_stop_whatsapp(android)
        automation.set_wifi_state(android, True)


def extract_database(backup, serial, key, output):
    if not serial:
        logging.error('No device serial provided')
        return
    
    if serial not in utils.get_adb_serials():
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
        utils.decrypt_whatsapp_database(enc_db_path, key, output)    
        logging.info(f'Database extracted!')


def generate_image(msg_store, locale, profile_pictures_dir, contacts, insighters, top_insighter, output):
    try:
        insighters_classes = [INSIGHTERS[i] for i in insighters]
    except KeyError as error:
        logging.error(f'Invalid insighter "{error.args[0]}"')
        return
    else:
        if top_insighter:
            if top_insighter not in INSIGHTERS:
                logging.error(f'Invalid insighter "{top_insighter}"')
                return
            insighters_classes.insert(0, INSIGHTERS[top_insighter])

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
                    contact_manager.update_contact_diplay_name(contact.jid, vcf_contact.display_name)
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
        winner = insighter.winner
        logging.info(f'{contact_manager.get(winner.jid).display_name}: {winner.formatted_value}')
        if winner.track_object:
            logging.info(f'{repr(winner.track_object)}')
        logging.info('')

    logging.info('Grouping contacts and profile pictures data...')
    image_contacts = dict()
    for contact in contact_manager.get_users():
        profile_picture = profile_pictures.get(contact.jid, contact.profile_image)
        if profile_picture:
            profile_picture = Image.open(io.BytesIO(base64.b64decode(profile_picture)))
        image_contacts[contact.jid] = contact.display_name, profile_picture
    
    logging.info('Generating the image...')
    top_insighter = top_insighter and insighter_manager.insighters[0]
    common_insighters = insighter_manager.insighters[1:] if top_insighter else insighter_manager.insighters
    user_profile_image_path = profile_pictures_dir and os.path.join(profile_pictures_dir, 'me.jpg')
    user_profile_image = user_profile_image_path if os.path.exists(user_profile_image_path) else None
    
    if not user_profile_image:
        logging.warning(f'User profile image not found in "{user_profile_image_path}"')

    create_insights_image(common_insighters, image_contacts, user_profile_image, top_insighter=top_insighter, output_path=output)


def generate_video(msg_store, locale, profile_pictures_dir, contacts, output):
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
    create_chart_race_video(contact_manager, message_manager, output, locale, group_contact_by_name=True)


def extract_profile_images(msg_store, output, chromedriver, update_existent_images=True):
    if not msg_store or not os.path.exists(msg_store):
        logging.error(f'Messages database not found in path "{msg_store}"')
        return
    
    if not output:
        logging.error('No output directory provided')
        return
    
    if output and os.path.exists(output) and not os.path.isdir(output):
        logging.error('The output path already exists and it\'s not directory')
        return
    
    if not chromedriver:
        logging.error('No chromedriver provided')
        return
    
    logging.info('Loading contacts...')
    contact_manager = ContactManager.from_msgtore_db(msg_store, from_me=True)

    os.makedirs(output, exist_ok=True)

    logging.info('Get your phone and be prepared to scan WhatsApp Web QR code. Press any key to continue...')
    input()

    logging.info('Logging into WhatsApp Web...')
    whatsapp_web = WhatsAppWeb(chromedriver)

    logging.info(f'Getting user profile image...')
    user_image_url = whatsapp_web.get_user_profile_image_url()
    with open(os.path.join(output, 'me.jpg'), 'wb') as file:
        response = requests.get(user_image_url)
        file.write(response.content)
        logging.info(f'User profile image has been saved!')

    for contact in contact_manager.get_users():
        phone_number = JID_REGEXP.search(contact.jid).group(1)
        output_image_path = os.path.join(output, f'{contact.jid}.jpg')
        if not os.path.exists(output_image_path) or update_existent_images:
            logging.info(f'Getting profile image for "{phone_number}"...')
            image_url = whatsapp_web.get_contact_profile_image_url(contact.jid)
            if image_url:
                with open(output_image_path, 'wb') as file:
                    response = requests.get(image_url)
                    file.write(response.content)
                logging.info(f'Profile image for "{phone_number}" has been saved!')
            else:
                logging.info(f'"{phone_number}" does not have profile image!')


def generate_rank_file(msg_store, locale, contacts, insighters, output):
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
    
    logging.info('Getting contact from vcf...')
    for contact in contact_manager.get_users():
        for vcf_contact in vcf_contact_manager.get_users():
            if utils.stringy_similarity(vcf_contact.jid, contact.jid) >= 0.95:
                if not contact.display_name:
                    contact_manager.update_contact_diplay_name(contact.jid, vcf_contact.display_name)
                break
    
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
    
    result = dict()

    with utils.context_locale(locale):
        for insighter in insighter_manager.insighters:
            properties = dict()
            properties['title'] = insighter.title
            properties['rank'] = []
            for rank_item in insighter.get_rank():
                contact = contact_manager.get(rank_item.jid)
                properties['rank'].append({
                    'jid': rank_item.jid,
                    'contact_name': contact and contact.display_name,
                    'value': rank_item.value,
                    'formatted_value': rank_item.formatted_value,
                    'date': rank_item.track_object and rank_item.track_object.date.strftime(RANK_DATE_FORMAT)
                })

            result[insighter.__class__.__name__] = properties

    with open(output, 'w') as file:
        json.dump(result, file, indent=4)


if __name__ == '__main__':
    default_device_serial = next(iter(utils.get_adb_serials(include_emulators=False)), None)

    parser = argparse.ArgumentParser(description='Collect insights from WhatsApp',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--debug', dest='debug', action='store_true', default=False, help='Log debug messages')

    subparsers = parser.add_subparsers(dest='command', description='commands')
    subparsers.required = True

    key_parser = subparsers.add_parser('extract-key', help='Extract WhatsApp database key',
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    key_parser.add_argument('--no-verify-apk', action='store_false', default=True, dest='verify_apk', 
                            help='Verify WhatsApp APK signature before install in the emulator')
    key_parser.add_argument('--no-backup', action='store_false', default=True, dest='backup', 
                            help='Do not backup WhatsApp messages before extracting the key (Not recommended).')
    key_parser.add_argument('--show-emulator', action='store_true', default=False, dest='show_emulator',
                            help='Show emulator window while the key extraction is happening')
    key_parser.add_argument('--serial', dest='serial', default=default_device_serial,
                            help='Serial device for backup WhatsApp messages')
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

    profile_images_parser = subparsers.add_parser('extract-profile-images', help='Extract contacts profile images',
                                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    profile_images_parser.add_argument('--msg-store', dest='msg_store', default='msgstore.db', help='WhatsApp database file path')
    profile_images_parser.add_argument('--output', dest='output', default='./profile_pictures', 
                                       help='Directory where to save the contacts profile images')
    profile_images_parser.add_argument('--chromedriver', dest='chromedriver', default=f'./{CHROMEDRIVER_BIN}', help='Chrome Driver path')
    profile_images_parser.add_argument('--update-existent-images', dest='update_existent_images', default=False, action='store_true',
                                       help='Extract contacts profile images even it is already downloaded')

    image_parser = subparsers.add_parser('generate-image', help='Generate Insights image',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    image_parser.add_argument('--msg-store', dest='msg_store', default='msgstore.db', help='WhatsApp database file path')
    image_parser.add_argument('--locale', dest='locale', default='en_US', help='Output language texts')
    image_parser.add_argument('--profile-pictures-dir', dest='profile_pictures_dir', default='./profile_pictures',
                              help='Directory to look for contact profile pictures. ' 
                                   'It will be used default profile picture when the program do not find')
    image_parser.add_argument('--contacts', dest='contacts', default='./contacts.vcf', help='Contacts export file path')
    image_parser.add_argument('--insighters', nargs='+', dest='insighters', choices=list(INSIGHTERS.keys()),
                              default=['LongestConversationInsighter', 'LongestAudioInsighter',
                                       'GreatestAudioAmountInsighter', 'GreatestPhotoAmountInsighter', 
                                       'GreatestAmountOfDaysTalkingInsighter', 'LongestTimeInCallsInsighter'])
    image_parser.add_argument('--top-insighter', dest='top_insighter', default='GreatestMessagesAmountInsighter',
                              help='Insigther result to show the top three in the image')
    image_parser.add_argument('--output', dest='output', default='./insights.png', help='Insights output image file')

    video_parser = subparsers.add_parser('generate-video', help='Generate Chart Race video',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    video_parser.add_argument('--msg-store', dest='msg_store', default='msgstore.db', help='WhatsApp database file path')
    video_parser.add_argument('--locale', dest='locale', default='en_US', help='Output language texts')
    video_parser.add_argument('--profile-pictures-dir', dest='profile_pictures_dir', default='./profile_pictures',
                              help='Directory to look for contact profile pictures. ' 
                                   'It will be used default profile picture when the program do not find')
    video_parser.add_argument('--contacts', dest='contacts', default='./contacts.vcf', help='Contacts export file path')
    video_parser.add_argument('--output', dest='output', default='./chart-race.mp4', help='Chart Race output video file')

    rank_parser = subparsers.add_parser('generate-rank-file', help='Generate JSON file containing the rank of each insighter',
                                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    rank_parser.add_argument('--msg-store', dest='msg_store', default='msgstore.db', help='WhatsApp database file path')
    rank_parser.add_argument('--locale', dest='locale', default='en_US', help='Output language texts')
    rank_parser.add_argument('--contacts', dest='contacts', default='./contacts.vcf', help='Contacts export file path')
    rank_parser.add_argument('--insighters', nargs='+', dest='insighters', choices=list(INSIGHTERS.keys()), 
                             default=list(INSIGHTERS.keys()))
    rank_parser.add_argument('--output', dest='output', default='./rank.json', help='Rank output JSON file')

    args = parser.parse_args()

    logging_level = logging.DEBUG if args.debug else logging.INFO

    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging_level)

    kwargs = vars(args)
    kwargs.pop('debug')
    globals()[kwargs.pop('command').replace('-', '_')](**kwargs)
