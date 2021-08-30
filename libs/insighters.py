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
        if not self._include_group and Contact.is_group(message.remote_jid):
            return

        for insighter in self._filter_insighters(MessageInsighter):
            if self._group_by_name:
                if message.remote_jid in self.contact_manager: 
                    contact = self.contact_manager[message.remote_jid]
                    common_contacts = self.contact_manager.get_contacts_by_display_name(contact.display_name)
                    message.remote_jid = common_contacts[-1].jid if common_contacts else message.remote_jid
            insighter.update(message)

    def _update_by_call(self, call):
        if not self._include_group and Contact.is_group(call.remote_jid):
            return

        for insighter in self._filter_insighters(CallInsighter):
            if self._group_by_name:
                if call.remote_jid in self.contact_manager: 
                    contact = self.contact_manager[call.remote_jid]
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

        self._winner = None
    
    @property
    def winner(self):
        value = self._winner and self.normalize_value(self._winner.value)
        return self._winner and Insighter.Winner(self._winner.jid, self._winner.data, 
                                                 self.format_value(value=value))
    
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
        # TODO
        pass

    @staticmethod
    def normalize_value(value):
        return value

    class Winner:
        def __init__(self, jid, data, value):
            self.jid = jid
            self.data = data
            self.value = value

        def __repr__(self):
            return f'{self.__class__.__name__}{(self.jid, self.data, self.value)}'


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
        if not self._winner or message.media_duration > self._winner.value \
            or (message.media_duration == self._winner.value and message.date < self._winner.data.date):
            self._winner = Insighter.Winner(message.remote_jid, message, message.media_duration)

    def normalize_value(self, value):
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
        self._rank[message.remote_jid] = self._rank.get(message.remote_jid, 0) + 1
        if not self._winner or self._rank[message.remote_jid] > self._winner.value:
            self._winner = Insighter.Winner(message.remote_jid, None, self._rank[message.remote_jid])


class GreatestPhotoAmountInsighter(MessageInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest amount of photo'
        format_ = format_ or '{value} photos'
        super().__init__(title, format_)

    def is_valid_data(self, message):
        return not message.from_me and Message.is_image(message.mime_type)

    def handle_data(self, message):
        self._rank[message.remote_jid] = self._rank.get(message.remote_jid, 0) + 1
        if not self._winner or self._rank[message.remote_jid] > self._winner.value:
            self._winner = Insighter.Winner(message.remote_jid, None, self._rank[message.remote_jid])


class GreatestAmountOfDaysTalkingInsighter(MessageInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest amount of days talking'
        format_ = format_ or '{value} days'
        self._total_days_rank = {}
        super().__init__(title, format_)

    def handle_data(self, message):
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


class LongestConversationInsighter(MessageInsighter):
    # To this insighter to work, the messages has to be ordered (ASC or DESC)
    
    # Max difference between messages time is 1 minute
    MAX_DIFF = 60

    def __init__(self, title=None, format_=None):
        title = title or 'Longest uninterrupted conversation'
        super().__init__(title, format_)

    def handle_data(self, message):
        if message.remote_jid not in self._rank:
            self._rank[message.remote_jid] = message, message, 0
        first_message, last_message, current_total = self._rank[message.remote_jid]
        message_diff_time = abs((message.date - last_message.date).total_seconds())

        if message_diff_time <= LongestConversationInsighter.MAX_DIFF:
            last_message = message
            current_total += message_diff_time
        else:
            first_message = last_message = message
            current_total = 0
        self._rank[message.remote_jid] = first_message, last_message, current_total

        if not self._winner or self._rank[message.remote_jid][2] > self._winner.value:
            self._winner = Insighter.Winner(message.remote_jid, first_message, current_total)

    def normalize_value(self, value):
        return time_delta_to_str(value, ['h', 'm', 's'])


class TopMessagesAmountInsighter(MessageInsighter):
    def __init__(self, title=None, format_=None, total=3):
        title = title or 'Top messages amount'
        format_ = format_ or '{value:,} messages'
        
        super().__init__(title, format_)
        
        self._total = total
        self._winner = [None] * total

    def handle_data(self, message):
        self._rank[message.remote_jid] = self._rank.get(message.remote_jid, 0) + 1

        podium = self._winner.copy()
        try:
            current_position = podium.index(message.remote_jid)
        except ValueError:
            podium.append(message.remote_jid)
            current_position = len(podium) - 1
        
        for i in range(current_position, 0, -1):
            if not podium[i - 1] or self._rank[podium[i]] > self._rank[podium[i - 1]]:
                podium[i], podium[i - 1] = podium[i - 1], podium[i]

        self._winner = podium[:len(self._winner)]
    
    @property
    def winner(self):
        winners = []
        for winner in self._winner:
            value = winner and self.format_value(self._rank[winner])
            winners.append(winner and Insighter.Winner(winner, None, value))
        return winners


class LongestCallInsighter(CallInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Longest call'
        super().__init__(title, format_)

    def handle_data(self, call):
        if not self._winner or call.duration > self._winner.value \
            or (call.duration == self._winner.value and call.date < self._winner.data.date):
            self._winner = Insighter.Winner(call.remote_jid, call, call.duration)

    def normalize_value(self, value):
        return time_delta_to_str(value, ['h', 'm', 's'])


class GreatestCallAmountInsighter(CallInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Greatest amount of calls'
        format_ = format_ or '{value} calls'
        super().__init__(title, format_)
    
    def is_valid_data(self, call):
        return call.duration > 0

    def handle_data(self, call):
        self._rank[call.remote_jid] = self._rank.get(call.remote_jid, 0) + 1
        if not self._winner or self._rank[call.remote_jid] > self._winner.value:
            self._winner = Insighter.Winner(call.remote_jid, None, self._rank[call.remote_jid])


class LongestTimeInCallsInsighter(CallInsighter):
    def __init__(self, title=None, format_=None):
        title = title or 'Longest time in calls'
        super().__init__(title, format_)
    
    def is_valid_data(self, call):
        return call.duration > 0

    def handle_data(self, call):
        self._rank[call.remote_jid] = self._rank.get(call.remote_jid, 0) + call.duration
        if not self._winner or self._rank[call.remote_jid] > self._winner.value:
            self._winner = Insighter.Winner(call.remote_jid, None, self._rank[call.remote_jid])

    def normalize_value(self, value):
        return time_delta_to_str(value, ['h', 'm', 's'])
