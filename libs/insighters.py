from datetime import datetime

from .calls import Call
from .messages import Message
from .contacts import Contact
from .utils import time_delta_to_str


class InsighterManager:
    def __init__(self, contact_manager, include_group=False, group_by_name=False):
        self._insighters = []
        self._group_by_name = group_by_name
        self._include_group = include_group
        self.contact_manager = contact_manager
    
    @property
    def insighters(self):
        return list(self._insighters)

    def add_insighter(self, insighter):
        assert isinstance(insighter, Insighter)
        self._insighters.append(insighter)
    
    def update(self, message_or_call):
        if isinstance(message_or_call, Message):
            return self._update_by_message(message_or_call)
        elif isinstance(message_or_call, Call):
            return self._update_by_call(message_or_call)
        raise TypeError('expecting Message or Call object')

    def _update_by_message(self, message):
        if message.remote_jid.endswith('@broadcast') or message.remote_jid.endswith('@temp') \
                or (not self._include_group and Contact.is_group(message.remote_jid)):
            return

        for insighter in self._filter_insighters(MessageInsighter):
            if self._group_by_name:
                contact = self.contact_manager.get(message.remote_jid)
                if contact and contact.display_name is not None:
                    common_contacts = self.contact_manager.get_contacts_by_display_name(contact.display_name)
                    message.remote_jid = common_contacts[-1].jid if common_contacts else message.remote_jid
            insighter.update(message)

    def _update_by_call(self, call):
        if not self._include_group and Contact.is_group(call.remote_jid):
            return

        for insighter in self._filter_insighters(CallInsighter):
            if self._group_by_name:
                contact = self.contact_manager.get(call.remote_jid)
                if call.remote_jid in self.contact_manager: 
                    if contact and contact.display_name is not None:
                        common_contacts = self.contact_manager.get_contacts_by_display_name(contact.display_name)
                        call.remote_jid = common_contacts[-1].jid if common_contacts else call.remote_jid
            insighter.update(call)

    def _filter_insighters(self, class_):
        return (insighter for insighter in self._insighters if class_ in insighter.__class__.__bases__)


class Insighter:
    """
    Do not extend this class directly, use a child class such as MessageInsighter and CallInsighter
    """
    def __init__(self, title, format_):
        self.title = title
        self.format = format_ or '{value}'
        self._rank = {}

    @property
    def winner(self):
        return max(self._rank.values(), key=lambda item: item.value)

    def update(self, data):
        if self.is_valid_data(data):
            self.handle_data(data)

    def is_valid_data(self, data):
        return True

    def handle_data(self, data):
        raise NotImplementedError

    def format_value(self, value):
        return self.format.format(value=value)
    
    def clear(self):
        self._winner = None
    
    def get_rank(self):
        return sorted(self._rank.values(), key=lambda item: item.value, reverse=True)

    def _set_contact_rank_value(self, jid, value, insighter_track_object=None):
        self._rank[jid] = Insighter.InsighterRankItem(jid, value, insighter_track_object, self.format_value)

    class InsighterRankItem:
        def __init__(self, jid, value, track_object, format_method=None):
            self.jid = jid
            self.value = value
            self.track_object = track_object
            self._format_method = format_method

        def __repr__(self):
            return f'{self.__class__.__name__}{(self.jid, self.value, self.track_object)}'
        
        @property
        def formatted_value(self):
            return self._format_method(self.value) if self._format_method else self.value


class MessageInsighter(Insighter):
    pass


class CallInsighter(Insighter):
    pass


class LongestAudioInsighter(MessageInsighter):
    def __init__(self, title=None, format_=None, check_media_name=True):
        """
        Create a Longest Audio Insighter
        :param check_media_name: If true the media name will be used to make sure the media is a voice message.
        """
        title = title or 'Longest audio message'
        self.check_media_name = check_media_name
        super().__init__(title, format_)
    
    def is_valid_data(self, message):
        return not message.from_me and Message.is_voice_message(message.mime_type) \
            and message.media_duration and not message.forwarded \
            and (not self.check_media_name or message.media_name and message.media_name.endswith('.opus'))

    def handle_data(self, message):
        jid = message.remote_jid 
        if jid not in self._rank or message.media_duration > self._rank[jid].value \
            or (message.media_duration == self._rank[jid].value and message.date < self._rank[jid].track_object.date):
            self._set_contact_rank_value(jid, message.media_duration, message)

    def format_value(self, value):
        return time_delta_to_str(value, ['h', 'm', 's'])

class GreatestAudioAmountInsighter(MessageInsighter):
    def __init__(self, title=None, format_=None, check_media_name=True):
        """
        Create a Greatest Audio Insighter
        :param check_media_name: If true the media name will be used to make sure the media is a voice message.
        """
        title = title or 'Greatest amount of audio'
        format_ = format_ or '{value} audios'
        self.check_media_name = check_media_name
        super().__init__(title, format_)

    def is_valid_data(self, message):
        return not message.from_me and Message.is_voice_message(message.mime_type) \
            and message.media_duration and not message.forwarded \
            and (not self.check_media_name or message.media_name and message.media_name.endswith('.opus'))

    def handle_data(self, message):
        current_value = self._rank[message.remote_jid].value if message.remote_jid in self._rank else 0
        self._set_contact_rank_value(message.remote_jid, current_value + 1)


class GreatestPhotoAmountInsighter(MessageInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest amount of photo'
        format_ = format_ or '{value} photos'
        super().__init__(title, format_)

    def is_valid_data(self, message):
        return not message.from_me and Message.is_image(message.mime_type)

    def handle_data(self, message):
        current_value = self._rank[message.remote_jid].value if message.remote_jid in self._rank else 0
        self._set_contact_rank_value(message.remote_jid, current_value + 1)


class GreatestAmountOfDaysTalkingInsighter(MessageInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest amount of days talking'
        format_ = format_ or '{value} days'
        self._days_messages = dict()
        super().__init__(title, format_)

    def handle_data(self, message):
        if message.remote_jid not in self._days_messages:
            self._days_messages[message.remote_jid] = dict()
        day = int(datetime.combine(message.date, message.date.min.time()).timestamp())
        if day not in self._days_messages[message.remote_jid]:
            self._days_messages[message.remote_jid][day] = 0b00
        if self._days_messages[message.remote_jid][day] != 0b11:
            self._days_messages[message.remote_jid][day] |= message.from_me << 1
            self._days_messages[message.remote_jid][day] |= not message.from_me
            current_value = self._rank[message.remote_jid].value if message.remote_jid in self._rank else 0
            if self._days_messages[message.remote_jid][day] == 0b11:
                self._set_contact_rank_value(message.remote_jid, current_value + 1)


class LongestConversationInsighter(MessageInsighter):
    # To this insighter to work, the messages has to be ordered (ASC or DESC)
    
    # Max difference between messages time is 1 minute
    MAX_DIFF = 60

    def __init__(self, title=None, format_=None):
        title = title or 'Longest uninterrupted conversation'
        self._conversation_messages = dict()
        super().__init__(title, format_)

    def handle_data(self, message):
        if message.remote_jid not in self._rank:
            self._conversation_messages[message.remote_jid] = message, message, 0
        first_message, last_message, current_total = self._conversation_messages[message.remote_jid]
        message_diff_time = abs((message.date - last_message.date).total_seconds())

        if message_diff_time <= LongestConversationInsighter.MAX_DIFF:
            last_message = message
            current_total += message_diff_time
        else:
            first_message = last_message = message
            current_total = 0

        self._conversation_messages[message.remote_jid] = first_message, last_message, current_total

        jid = message.remote_jid 
        if message.remote_jid not in self._rank or current_total > self._rank[jid].value:
            self._set_contact_rank_value(message.remote_jid, current_total, first_message)

    def format_value(self, value):
        return time_delta_to_str(value, ['h', 'm', 's'])


class GreatestMessagesAmountInsighter(MessageInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest messages amount'
        format_ = format_ or '{value:,} messages'
        
        super().__init__(title, format_)
        
    def handle_data(self, message):
        current_value = self._rank[message.remote_jid].value if message.remote_jid in self._rank else 0
        self._set_contact_rank_value(message.remote_jid, current_value + 1)


class LongestCallInsighter(CallInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Longest call'
        super().__init__(title, format_)

    def handle_data(self, call):
        jid = call.remote_jid 
        if jid not in self._rank or call.duration > self._rank[jid].value \
            or (call.duration == self._rank[jid].value and call.date < self._rank[jid].track_object.date):
            self._set_contact_rank_value(jid, call.duration, call)

    def format_value(self, value):
        return time_delta_to_str(value, ['h', 'm', 's'])


class GreatestCallAmountInsighter(CallInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest amount of calls'
        format_ = format_ or '{value} calls'
        super().__init__(title, format_)
    
    def is_valid_data(self, call):
        return call.duration > 0

    def handle_data(self, call):
        current_value = self._rank[call.remote_jid].value if call.remote_jid in self._rank else 0
        self._set_contact_rank_value(call.remote_jid, current_value + 1)


class LongestTimeInCallsInsighter(CallInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Longest time in calls'
        super().__init__(title, format_)
    
    def is_valid_data(self, call):
        return call.duration > 0

    def handle_data(self, call):
        current_value = self._rank[call.remote_jid].value if call.remote_jid in self._rank else 0
        self._set_contact_rank_value(call.remote_jid, current_value + call.duration)

    def format_value(self, value):
        return time_delta_to_str(value, ['h', 'm', 's'])
