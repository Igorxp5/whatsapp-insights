import os
import re
import base64
import typing
import sqlite3
import vobject
import logging
import itertools

from . import utils
from .type import Jid, Base64Image, FilePath, DirPath
from .export_chats import parse_export_chat_file, EXPORT_CHAT_FILE_NAME

vobject.vcard.wacky_apple_photo_serialize = False

USER_JID_SUFFIX = 's.whatsapp.net'
JID_REGEXP = re.compile(r'((\d+)(-(\d+))?)@(s.whatsapp.net|g.us)')

TContactManager = typing.TypeVar('TContactManager', bound='ContactManager')

class Contact:
    USER_REGEXP = re.compile(r'(.+)@(s.whatsapp.net|c.us)')
    GROUP_REGEXP = re.compile(r'(.+)@g.us')

    def __init__(self, jid: Jid, display_name: str):
        self.jid: Jid = jid
        self.display_name: str = display_name
        self.contact_id: str = self.jid.split(USER_JID_SUFFIX, 1)[0]
        self.profile_image: Base64Image = None

    @property
    def phone_number(self) -> str:
        return self.contact_id

    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.jid)}, {repr(self.display_name)})'
    
    def __hash__(self):
        return hash(f'_____{self.__class__.__name__}_____{repr(self.jid)}_____')

    def to_vcard(self) -> str:
        vcard = vobject.vCard()
        vcard.add('TEL').value = f'+{self.contact_id}'
        if self.display_name:
            vcard.add('FN').value = self.display_name
            vcard.add('N').value = vobject.vcard.Name(family=self.display_name.split(' ')[-1], given=self.display_name.split(' ')[:-1])
        else:
            vcard.add('FN').value = self.display_name
        if self.profile_image:
            vcard.add('PHOTO;ENCODING=b;image/png').value = self.profile_image
        return vcard.serialize()
    
    @staticmethod
    def is_user(jid: Jid) -> bool:
        return bool(Contact.USER_REGEXP.match(jid))
    
    @staticmethod
    def is_group(jid: Jid) -> bool:
        return bool(Contact.GROUP_REGEXP.match(jid))


class ContactManager:
    def __init__(self):
        self._users: typing.Dict[Jid, Contact] = dict()
        self._groups: typing.Dict[Jid, Contact] = dict()
        self._display_names: typing.Dict[str, typing.Set[Contact]] = dict()

    def __getitem__(self, jid: Jid) -> Contact:
        return self._get_jid_dictionary(jid)[jid]
    
    def __delitem__(self, jid: Jid):
        del self._get_jid_dictionary(jid)[jid]
    
    def __contains__(self, jid: Jid) -> bool:
        return self.get(jid) is not None
    
    def __iter__(self) -> typing.Iterator[Contact]:
        return itertools.chain(self._users.values(), self._groups.values())
    
    def get(self, jid: Jid, default=None) -> Contact:
        try:
            return self._get_jid_dictionary(jid).get(jid, default)
        except ValueError:
            return default

    def get_users(self) -> typing.Iterable:
        return self._users.values()
    
    def get_groups(self):
        return self._groups.values()

    def add_contact(self, jid: Jid, display_name: str) -> Contact:
        contact = Contact(jid, display_name)
        self._get_jid_dictionary(jid)[jid] = contact
        if self._get_jid_dictionary(jid) is self._users:
            self._display_names.setdefault(contact.display_name, set())
            self._display_names[contact.display_name].add(contact)
        return contact
    
    def update_contact_diplay_name(self, jid: Jid, display_name: str):
        if self._get_jid_dictionary(jid) is self._users:
            contact = self.get(jid)
            self._display_names.setdefault(contact.display_name, set())
            self._display_names[contact.display_name].remove(contact)
            contact.display_name = display_name
            self._display_names.setdefault(display_name, set())
            self._display_names[display_name].add(contact)

    def get_contacts_by_display_name(self, display_name: str) -> typing.List[Contact]:
        return list(self._display_names.get(display_name, []))
    
    def export_vcf(self, filepath: FilePath, include_groups: bool=False):
        contacts = self.get_users() if not include_groups else iter(self)
        content = '\n'.join(contact.to_vcard() for contact in contacts)
        with open(filepath, 'w') as file:
            file.write(content)

    def update(self, other_contact_manager: TContactManager,
               by_display_name_similarity=False, by_jid_similarity=True,
               overwrite_display_name: typing.Union[bool, None]=True,
               overwrite_profile_image: typing.Union[bool, None]=True):
        """
        Update contacts properties in the ContactManager object using another ContactManager. Contacts
        not present in the origin object will be added.

        :param other_contact_manager: The other ContactManager object
        :param by_display_name_similarity: Find contacts with similar display name to update (match is not required)
        :param by_jid_similarity: Find contacts with similar jid to update (match is not required)
        :param overwrite_display_name: Set overwrite behavior for contact display name to other's contact display name.
            Case True, the contact display name will be overwritten when an other's contact is found in the origin ContactManager.
            Case False, the contact display name will not be overwritten.
            Case None, the contact display name will be overwriteen just if origin contact does not have a display name
        :param overwrite_profile_image: Set overwrite behavior for contact profile image to other's contact profile image.
            Case True, the contact contact profile image will be overwritten when an other's contact is found in the origin ContactManager.
            Case False, the contact contact profile image will not be overwritten.
            Case None, the contact contact profile image will be overwriteen just if origin contact does not have a contact profile image
        """
        for other_contact in other_contact_manager:
            self_contact = self.get(other_contact.jid)
            if self_contact and (overwrite_display_name or (overwrite_display_name is None and self_contact.display_name is None)):
                self.update_contact_diplay_name(other_contact.jid, other_contact.display_name)
            elif not self_contact:
                self_contact = self.add_contact(other_contact.jid, other_contact.display_name)
            if overwrite_profile_image or (overwrite_profile_image is None and self_contact.profile_image is None):
                self_contact.profile_image = other_contact.profile_image

        if by_display_name_similarity or by_jid_similarity:
            for self_contact in self:
                for other_contact in other_contact_manager:
                    similar_jid = by_jid_similarity and utils.string_similarity(self_contact.jid, other_contact.jid) >= 0.95
                    similar_name = by_display_name_similarity and self_contact.display_name and other_contact.display_name and \
                        utils.string_similarity(self_contact.display_name, other_contact.display_name) >= 0.95

                    if similar_jid or similar_name:
                        if overwrite_display_name or (overwrite_display_name is None and self_contact.display_name is None):
                            self.update_contact_diplay_name(self_contact.jid, other_contact.display_name)
                        if overwrite_profile_image or (overwrite_profile_image is None and self_contact.profile_image is None):
                            self_contact.profile_image = other_contact.profile_image


    def _get_jid_dictionary(self, jid: Jid) -> typing.Dict[str, Contact]:
        if Contact.is_user(jid):
            return self._users
        elif Contact.is_group(jid):
            return self._groups
        raise ValueError(f'contact {jid} not found')

    @staticmethod
    def from_wa_db(db_path: FilePath) -> TContactManager:
        with sqlite3.connect(db_path) as conn:
            contact_manager = ContactManager()
            for row in conn.execute('SELECT * FROM wa_contacts'):
                jid = row[1]
                display_name = row[7]
                if JID_REGEXP.match(jid):
                    contact_manager.add_contact(jid, display_name)
        return contact_manager

    @staticmethod
    def from_msgtore_db(db_path: FilePath, from_me: bool=True) -> TContactManager:
        with sqlite3.connect(db_path) as conn:
            contact_manager = ContactManager()

            where_condition = ''
            if from_me:
                where_condition = 'WHERE from_me = 1'

            sql = 'SELECT jid.raw_string FROM message ' \
                  'INNER JOIN chat ON message.chat_row_id = chat._id ' \
                  'INNER JOIN jid ON chat.jid_row_id = jid._id ' \
                  f'{where_condition} GROUP BY jid.raw_string'

            for row in conn.execute(sql):
                jid = row[0]
                display_name = None
                if JID_REGEXP.match(jid):
                    contact_manager.add_contact(jid, display_name)
        return contact_manager
    
    @staticmethod
    def from_vcf(file_path: FilePath) -> TContactManager:
        contact_manager = ContactManager()
        raw = None
        with open(file_path, encoding='utf-8') as file:
            raw = file.read()
        try:
            for entry in vobject.readComponents(raw, allowQP=True):
                if hasattr(entry, 'tel'):
                    for tel in entry.contents['tel']:
                        phone_number = re.sub(r'[\(\s\)]', '', tel.value)
                        jid = phone_number.strip('+') + '@s.whatsapp.net'
                        display_name = entry.fn.value if hasattr(entry, 'fn') else phone_number
                        contact = contact_manager.add_contact(jid, display_name)
                        if hasattr(entry, 'photo'):
                            contact.profile_image = base64.b64encode(entry.photo.value).decode('ascii')
        except vobject.base.ParseError:
            logging.warning('Failed to parse some entries in the vcf file')
        return contact_manager

    @staticmethod
    def from_export_chats_folder(chats_folder: DirPath) -> TContactManager:
        contact_manager = ContactManager()

        chat_files = [file for file in os.listdir(chats_folder) if EXPORT_CHAT_FILE_NAME.match(file)]
        for chat_file in chat_files:
            chat_file = os.path.join(chats_folder, chat_file)

            messages = parse_export_chat_file(chat_file)

            for message in messages:
                if message.dummy_jid not in contact_manager:
                    contact_manager.add_contact(message.dummy_jid, message.contact_name)

        return contact_manager


if __name__ == '__main__':
    contact_manager = ContactManager.from_wa_db('wa.db')
