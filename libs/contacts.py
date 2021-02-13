import re
import sqlite3

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
    
    def get(self, jid, default=None):
        try:
            return self._get_jid_dictionary(jid).get(jid, default)
        except ValueError:
            return default

    def add_contact(self, jid, display_name):
        contact = Contact(jid, display_name)
        self._get_jid_dictionary(jid)[jid] = contact
        if self._get_jid_dictionary(jid)[jid] is self._users:
            if contact.display_name not in self._display_names:
                self._display_names[contact.display_name] = []
            self._display_names[contact.display_name].append(contact)

    def get_contacts_by_display_name(self, display_name):
        return list(self._display_names.get(display_name, []))
    
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
                if not jid.endswith('broadcast'):
                    contact_manager.add_contact(jid, display_name)
        return contact_manager

class Contact:
    JID_REGEXP = re.compile(r'(.+)@(.+)')
    USER_REGEXP = re.compile(r'(.+)@(s.whatsapp.net|c.us)')
    GROUP_REGEXP = re.compile(r'(.+)@g.us')

    def __init__(self, jid, display_name):
        self.jid = jid
        self.display_name = display_name
        self.contact_id = Contact.JID_REGEXP.search(self.jid).group(0)
    
    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.jid)}, {repr(self.display_name)})'
    
    @staticmethod
    def is_user(jid):
        return bool(Contact.USER_REGEXP.match(jid))
    
    @staticmethod
    def is_group(jid):
        return bool(Contact.GROUP_REGEXP.match(jid))


if __name__ == '__main__':
    contact_manager = ContactManager.from_wa_db('wa.db')
