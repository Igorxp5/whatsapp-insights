from datetime import datetime

from .messages import Message


class InsighterManager:
    def __init__(self, contact_manager, group_by_name=False):
        self._insighters = []
        self._group_by_name = group_by_name
        self.contact_manager = contact_manager
    
    @property
    def insighters(self):
        return list(self._insighters)

    def add_insighter(self, insighter):
        assert isinstance(insighter, Insighter)
        self._insighters.append(insighter)
    
    def update(self, message):
        assert isinstance(message, Message)

        for insighter in self._insighters:
            if self._group_by_name:
                if message.remote_jid in self.contact_manager: 
                    contact = self.contact_manager[message.remote_jid]
                    common_contacts = self.contact_manager.get_contacts_by_display_name(contact.display_name)
                    message.remote_jid = common_contacts[-1].jid if common_contacts else message.remote_jid
            insighter.update(message)


class Insighter:
    def __init__(self, title, format_):
        self.title = title
        self.format = format_ or '{value}'
        self._rank = {}

        self._winner = None
    
    @property
    def winner(self):
        return self._winner and  Insighter.Winner(self._winner.jid, self._winner.message, 
                                                  self.normalize_value(self._winner.value))
    
    def update(self, message):
        if self.is_valid_message(message):
            self.handle_message(message)

    def handle_message(self):
        raise NotImplementedError

    def format_value(self, value):
        return self.format.format(value=value)
    
    def clear(self):
        self._winner = None
    
    @staticmethod
    def normalize_value(value):
        return str(value)

    class Winner:
        def __init__(self, jid, message, value):
            self.jid = jid
            self.message = message
            self.value = value

        def __repr__(self):
            return f'{self.__class__.__name__}{(self.jid, self.message, self.value)}'


class LongestAudioInsighter(Insighter):
    def __init__(self, title=None, format_=None, check_media_name=True):
        """
        Create a Longest Audio Insighter
        :param check_media_name: If true the media name will be used to make sure the media is a voice message.
        """
        title = title or 'Longest audio message'
        self.check_media_name = check_media_name
        super().__init__(title, format_)
    
    def is_valid_message(self, message):
        return not message.from_me and Message.is_voice_message(message.mime_type) \
            and message.media_duration and not message.forwarded \
            and (not self.check_media_name or message.media_name and message.media_name.endswith('.opus'))

    def handle_message(self, message):
        if not self._winner or message.media_duration > self._winner.value \
            or (message.media_duration == self._winner.value and message.date < self._winner.message.date):
            self._winner = Insighter.Winner(message.remote_jid, message, message.media_duration)


class GreatestAudioAmountInsighter(Insighter):
    def __init__(self, title=None, format_=None, check_media_name=True):
        """
        Create a Greatest Audio Insighter
        :param check_media_name: If true the media name will be used to make sure the media is a voice message.
        """
        title = title or 'Greatest amount of audio'
        self.check_media_name = check_media_name
        super().__init__(title, format_)

    def is_valid_message(self, message):
        return not message.from_me and Message.is_voice_message(message.mime_type) \
            and message.media_duration and not message.forwarded \
            and (not self.check_media_name or message.media_name and message.media_name.endswith('.opus'))

    def handle_message(self, message):
        self._rank[message.remote_jid] = self._rank.get(message.remote_jid, 0) + 1
        if not self._winner or self._rank[message.remote_jid] > self._winner.value:
            self._winner = Insighter.Winner(message.remote_jid, None, self._rank[message.remote_jid])


class GreatestPhotoAmountInsighter(Insighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest amount of photo'
        super().__init__(title, format_)

    def is_valid_message(self, message):
        return not message.from_me and Message.is_image(message.mime_type)

    def handle_message(self, message):
        self._rank[message.remote_jid] = self._rank.get(message.remote_jid, 0) + 1
        if not self._winner or self._rank[message.remote_jid] > self._winner.value:
            self._winner = Insighter.Winner(message.remote_jid, None, self._rank[message.remote_jid])


class GreatestAmountOfDaysTalkingInsighter(Insighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest amount of days talking'
        format_ = format_ or '{value} days'
        self._total_days_rank = {}
        super().__init__(title, format_)

    def is_valid_message(self, message):
        return True

    def handle_message(self, message):
        if message.remote_jid not in self._rank:
            self._rank[message.remote_jid] = {}
            self._total_days_rank[message.remote_jid] = 0
        day = int(datetime.combine(message.date, message.date.min.time()).timestamp())
        if day not in self._rank[message.remote_jid]:
            self._rank[message.remote_jid][day] = 0b00
        if self._rank[message.remote_jid][day] != 0b11:
            self._rank[message.remote_jid][day] |= message.from_me << 1
            self._rank[message.remote_jid][day] |= not message.from_me
            self._total_days_rank[message.remote_jid] += 1 if self._rank[message.remote_jid][day] == 0b11 else 0
            if not self._winner or self._total_days_rank[message.remote_jid] > self._winner.value:
                self._winner = Insighter.Winner(message.remote_jid, None, self._total_days_rank[message.remote_jid])
