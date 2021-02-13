from libs.insighters import InsighterManager, LongestAudioInsighter
from libs.contacts import ContactManager
from libs.messages import MessageManager


contact_manager = ContactManager.from_wa_db('wa.db')
message_manager = MessageManager.from_msgstore_db('msgstore.db')

insighter_manager = InsighterManager(contact_manager, group_by_name=True)
longest_audio_insighter = LongestAudioInsighter()
insighter_manager.add_insighter(longest_audio_insighter)

for message in message_manager:
    insighter_manager.update(message)

print(insighter_manager)
