import sqlite3

from datetime import datetime


class CallManager:
    def __init__(self):
        self._calls = {}
    
    def __getitem__(self, jid):
        return self._calls[jid]
    
    def __iter__(self):
        return (call for calls in self._calls.values() for call in calls)
    
    @staticmethod
    def from_msgstore_db(db_path, tz=None):
        with sqlite3.connect(db_path) as conn:
            call_manager = CallManager()
            for row in conn.execute('SELECT jid.raw_string, call_log.from_me, call_log.timestamp, call_Log.video_call, call_log.duration, call_log.call_result FROM call_log ' \
                                    'INNER JOIN jid ON call_log.jid_row_id = jid._id'):
                remote_jid, from_me, timestamp, video_call, duration, call_result = row
                call = Call(remote_jid, from_me, timestamp / 1000, video_call, duration, call_result, tz=tz)
                if remote_jid not in call_manager._calls:
                    call_manager._calls[remote_jid] = []
                call_manager._calls[remote_jid].append(call)
        return call_manager


class Call:
    def __init__(self, remote_jid, from_me, date, video_call, duration, result, tz=None):
        self.remote_jid = remote_jid
        self.from_me = bool(from_me)
        self.date = datetime.fromtimestamp(date, tz=tz) if not isinstance(date, datetime) else date
        self.is_video_call = bool(video_call)
        self.duration = duration
        self.result = result

    def __repr__(self):
        return f'{self.__class__.__name__}{(self.remote_jid, self.from_me, self.date, self.is_video_call, self.duration, self.result)}'
