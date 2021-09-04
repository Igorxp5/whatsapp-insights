import re
import base64
import sqlite3
import vobject
import logging
import itertools

vobject.vcard.wacky_apple_photo_serialize = False

JID_REGEXP = re.compile(r'((\d+)(-(\d+))?)@(s.whatsapp.net|g.us)')


class ContactManager:
    def __init__(self):
        self._users = {}
        self._groups = {}
        self._display_names = {}
    
    def __getitem__(self, jid):
        return self._get_jid_dictionary(jid)[jid]
    
    def __delitem__(self, jid):
        del self._get_jid_dictionary(jid)[jid]
    
    def __contains__(self, jid):
        return self.get(jid) is not None
    
    def __iter__(self):
        return itertools.chain(self._users.values(), self._groups.values())
    
    def get(self, jid, default=None):
        try:
            return self._get_jid_dictionary(jid).get(jid, default)
        except ValueError:
            return default

    def get_users(self):
        return self._users.values()
    
    def get_groups(self):
        return self._groups.values()

    def add_contact(self, jid, display_name):
        contact = Contact(jid, display_name)
        self._get_jid_dictionary(jid)[jid] = contact
        if self._get_jid_dictionary(jid) is self._users:
            if contact.display_name not in self._display_names:
                self._display_names[contact.display_name] = []
            self._display_names[contact.display_name].append(contact)
        return contact
    
    def update_contact_diplay_name(self, jid, display_name):
        if self._get_jid_dictionary(jid) is self._users:
            contact = self.get(jid)
            contact.display_name = display_name
            if contact.display_name not in self._display_names:
                self._display_names[contact.display_name] = []
            self._display_names[contact.display_name].append(contact)

    def get_contacts_by_display_name(self, display_name):
        return list(self._display_names.get(display_name, []))
    
    def export_vcf(self, filepath, include_groups=False):
        contacts = self.get_users() if not include_groups else iter(self)
        content = '\n'.join(contact.to_vcard() for contact in contacts)
        with open(filepath, 'w') as file:
            file.write(content)
    
    def _get_jid_dictionary(self, jid):
        if Contact.is_user(jid):
            return self._users
        elif Contact.is_group(jid):
            return self._groups
        raise ValueError(f'contact {jid} not found')

    @staticmethod
    def from_wa_db(db_path):
        with sqlite3.connect(db_path) as conn:
            contact_manager = ContactManager()
            for row in conn.execute('SELECT * FROM wa_contacts'):
                jid = row[1]
                display_name = row[7]
                if JID_REGEXP.match(jid):
                    contact_manager.add_contact(jid, display_name)
        return contact_manager

    @staticmethod
    def from_msgtore_db(db_path):
        with sqlite3.connect(db_path) as conn:
            contact_manager = ContactManager()
            for row in conn.execute('SELECT key_remote_jid FROM messages GROUP BY key_remote_jid'):
                jid = row[0]
                display_name = None
                if JID_REGEXP.match(jid):
                    contact_manager.add_contact(jid, display_name)
        return contact_manager
    
    @staticmethod
    def from_vcf(file_path):
        contact_manager = ContactManager()
        with open(file_path) as file:
            try:
                for entry in vobject.readComponents(file):
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


class Contact:
    USER_REGEXP = re.compile(r'(.+)@(s.whatsapp.net|c.us)')
    GROUP_REGEXP = re.compile(r'(.+)@g.us')

    def __init__(self, jid, display_name):
        self.jid = jid
        self.display_name = display_name
        self.contact_id = JID_REGEXP.search(self.jid).group(1)
        self.profile_image = None
    
    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.jid)}, {repr(self.display_name)})'
    
    def to_vcard(self):
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
    def is_user(jid):
        return bool(Contact.USER_REGEXP.match(jid))
    
    @staticmethod
    def is_group(jid):
        return bool(Contact.GROUP_REGEXP.match(jid))


if __name__ == '__main__':
    contact_manager = ContactManager.from_wa_db('wa.db')
