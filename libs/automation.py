from libs import contacts
import re
import time
import getpass
import logging
import subprocess

from .android import WaitforTimeout, NotReachedToWindowError, NotReachedToActivityError


class UserDoesNotExist(RuntimeError):
    def __init__(self, *args):
        super().__init__(*args)


class FailedToDownloadAPK(RuntimeError):
    def __init__(self, *args):
        super().__init__(*args)


class SigntureMathError(RuntimeError):
    def __init__(self, *args):
        super().__init__(*args)


def open_whatsapp(android):
    android.start_activity('com.whatsapp/.Main', ['-a', 'android.intent.action.MAIN'])
    # handle_two_factor_verification(android)

def uninstall_whatsapp(android):
    android.uninstall_app('com.whatsapp')

def clear_whatsapp_data(android):
    android.clear_app('com.whatsapp')

def force_stop_whatsapp(android):
    android.force_stop('com.whatsapp')

def handle_two_factor_verification(android, timeout=5):
    # FIXME
    try:
        android.waitfor_window('com.whatsapp/com.whatsapp.HomeActivity', r'gr=CENTER', timeout=5)
    except NotReachedToWindowError:
        pass
    else:
        logging.warning('Whatsapp is requesting Two-step Verification!')
        code = getpass.getpass('Type your two-step verification code: ')
        if not android.is_keyboard_up():
            window_size = android.window_size()
            android.tap(window_size['width'] // 2, window_size['height'] // 2)
        android.text(code, step=3)

def extract_whatsapp_key(android, output_path):
    clear_whatsapp_data(android)

    open_whatsapp(android)
    
    try:
        android.ui.waitfor_element(text=re.compile(r'You have a custom ROM installed.'))
    except WaitforTimeout:
        pass
    else:
        logging.info('Closing Custom ROM popup...')
        time.sleep(2)
        android.ui.waitfor_element(text='OK').tap()

    # Check if is already logged
    logging.info('Agreeing with the Terms of Service...')
    android.ui.waitfor_element(text='AGREE AND CONTINUE').tap()
    android.ui.waitfor_element(id='registration_country').tap()

    logging.info('Opening Country code search menu...')
    android.ui.waitfor_element(id='menuitem_search').tap()
    android.ui.waitfor_element(id='search_src_text').tap()

    country_code = input('Digit your country code (eg: 55): ')
    phone = input('Digit your phone number: ')

    android.text(country_code)
    logging.info('Opening Country code search menu...')
    android.ui.waitfor_element(id='country_code', text=f'+{country_code}').tap()
    
    logging.info('Typing phone number...')
    android.ui.waitfor_element(id='registration_phone').tap()
    android.text(phone)
    
    logging.info('Confirming phone number...')
    android.ui.waitfor_element(text='NEXT').tap()
    android.ui.waitfor_element(text=re.compile(r'Is this OK, or would you like to edit the number?'))
    android.ui.waitfor_element(text='OK').tap()

    try:
        android.ui.waitfor_element(text=re.compile(r'To easily verify your number'))
    except WaitforTimeout:
        pass
    else:
        logging.info('Granting SMS permissions...')
        android.ui.waitfor_element(text='CONTINUE').tap()
        android.ui.waitfor_element(text='ALLOW').tap()

    logging.info('Checking if it is in Verify Phone Number screen...')
    android.waitfor_activity('com.whatsapp/.registration.VerifyPhoneNumber', timeout=10)
    logging.info('Reached to Verify Phone Number screen!')
    
    try:
        android.ui.waitfor_element(text=re.compile(r'send an SMS with your code'), timeout=7)
    except WaitforTimeout:
        pass
    else:
        wait_time = android.ui.find_element(id='resend_sms_btn').text().split('in', 1)[-1].strip()
        logging.warning(f'WhatsApp cannot send you an SMS because you\'ve tried to register recently. You can retry in {wait_time}') 
        logging.info('Using "Call me" option. Listen the code in the call.')
        if android.is_keyboard_up():
            android.back()
        android.ui.waitfor_element(text='Call me').tap()
        android.ui.waitfor_element(id='verify_sms_code_input').tap()

    logging.info('Whatsapp is requesting 6-digit code!')
    code = input('Type 6-digit code: ')

    logging.info('Typing 6-digit code...')
    android.text(code, step=3)

    handle_two_factor_verification(timeout=10)
    
    try:
        android.ui.waitfor_element(text='CONTINUE').tap()
    except WaitforTimeout:
        pass
    else:
        logging.info('Granting contacts permissions...')
        android.ui.waitfor_element(text='Allow').tap()
        time.sleep(3)
        android.ui.waitfor_element(text='Allow').tap()

    logging.info('Tapping to restore backup...')
    android.ui.waitfor_element(text='RESTORE').tap()

    time.sleep(10)

    force_stop_whatsapp(android)

    logging.info('Extracting database key...')
    android.pull('/data/data/com.whatsapp/files/key', output_path)

def open_whatsapp_chat(android, phone_number):
    android.shell(['am', 'start', '-d', f'smsto:{phone_number}', '-a', 'android.intent.action.SENDTO', 
                   '--activity-clear-top', '--activity-single-top', 'com.whatsapp'])
    try:
        android.waitfor_activity('com.whatsapp/.Conversation', timeout=5)
    except NotReachedToActivityError:
        if android.current_activity() == 'com.whatsapp/.conversationslist.SmsDefaultAppWarning':
            raise UserDoesNotExist('tried open chat of a user that does not exist')
        raise RuntimeError('unexpected screen')

def open_contact_info(android, jid):
    try:
        android.start_activity('com.whatsapp/.chatinfo.ContactInfoActivity',
                               ['-W', '--es', 'jid', jid, '--activity-clear-top', '--activity-single-top'])
    except subprocess.CalledProcessError:
        raise UserDoesNotExist(jid)
    try:
        android.ui.waitfor_element(id='conversation_contact_name', timeout=3)
    except WaitforTimeout:
        raise UserDoesNotExist(jid)

def get_contact_profile_info(android, jid):
    """
    Open Contact Info, get contact name and pull profile photo
    :return contact name
    """
    force_stop_whatsapp(android)
    open_contact_info(android, jid)
    android.ui.waitfor_element(id='header_placeholder').tap()
    crop_bounds = android.ui.waitfor_element(id='picture_animation').bounds()
    return android.ui.waitfor_element(id='conversation_contact_name').text(), android.screenshot(crop_bounds)

def get_user_profile_picture(android):
    open_whatsapp(android)
    crop_bounds = android.ui.waitfor_element(id='picture_animation').bounds()
    return android.screenshot(crop_bounds)

def install_whatsapp(android, apk_file, sdk_manager=None, apk_signature=None):
    if apk_signature:
        if not sdk_manager:
            raise RuntimeError('SDKManager object needed to verify apk signture')
        logging.info('Checking WhatsApp APK signature...')
        if sdk_manager.get_apk_sha256_signature(apk_file) != apk_signature:
            logging.error('WhatsApp APK does not have same signature of Official APK')
            raise SigntureMathError('WhatsApp APK does not have same signature of Official APK')

    logging.info('Installing WhatsApp APK...')
    android.adb(['install', '-r', '-d', '-g', apk_file])


def open_whatsapp_contact_info(android, phone_number):
    open_whatsapp_chat(phone_number)
    android.waitfor_element(id='conversation_contact_photo').tap()

def open_whatsapp_backup_activity(android):
    android.start_activity('com.whatsapp/.backup.google.SettingsGoogleDrive')

def backup_whatsapp_messages(android, timeout=600):
    open_whatsapp(android)
    android.ui.waitfor_element(contentDesc='More options').tap()
    android.ui.waitfor_element(text='Settings').tap()
    android.ui.waitfor_element(text='Chats').tap()
    android.scroll_down()
    android.ui.waitfor_element(text='Chat backup').tap()

    android.ui.waitfor_element(text='BACK UP').tap()
    
    start_time = time.time()
    while android.ui.find_element(text='Backing up messages', force_dump=True) and time.time() - start_time < timeout:
        pass

    if time.time() - start_time >= timeout:
        raise RuntimeError('timeout reached to WhatsApp finish to back up')

def set_wifi_state(android, enable):
    android.shell(['svc', 'wifi', 'enable' if enable else 'disable'])


def get_main_screen_contacts_info(android, include_groups=True, include_archive=True):
    # TODO: Include archive
    contacts = dict()
    open_whatsapp(android)
    while not android.ui.find_element(id='conversations_row_tip_tv'):
        android.ui.waitfor_element(id='contact_photo')
        current_page_contacts = android.ui.find_elements(id='conversations_row_contact_name')
        current_page_photos = android.ui.find_elements(id='contact_photo')

        for photo_element, contact_element in zip(current_page_photos, current_page_contacts):
            android.ui.waitfor_element(id='contact_photo')
            display_name = contact_element.text()
            logging.info(f'Getting contact info for "{display_name}"...')
            photo_element.tap()
            logging.info(f'Opening contact info...')
            try:
                android.ui.waitfor_element(id='info_btn').tap()
            except WaitforTimeout:
                logging.info(f'"{display_name}" is an invalid contact, ignoring it...')
                continue
            is_group = bool(android.ui.find_element(id='group_description') or android.ui.find_element(id='no_description_view'))
            if is_group:
                logging.info(f'Contact is a group')
            else:
                logging.info(f'Contact is not a group')
            if include_groups or not is_group:
                logging.info(f'Getting contact picture...')
                android.ui.waitfor_element(id='header_placeholder').tap()
                try:
                    crop_bounds = android.ui.waitfor_element(id='picture_animation', timeout=3).bounds()
                except WaitforTimeout:
                    logging.info(f'Contact "{display_name}" does not have profile picture')
                    photo = None
                else:
                    photo = android.screenshot(crop_bounds)
                    android.back()
                    android.ui.waitfor_element(id='header_placeholder')
                android.scroll_down()
                try:
                    phone_number = android.ui.waitfor_element(id='title_tv', timeout=5).text()
                except WaitforTimeout:
                    phone_number = display_name
                logging.info(f'Contact phone number: {phone_number}')
                contacts[phone_number] = display_name, photo, is_group
            android.back()
        android.scroll_down()
    return contacts
