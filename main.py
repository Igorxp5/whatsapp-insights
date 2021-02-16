from libs.insighters import InsighterManager, LongestAudioInsighter, \
    GreatestAudioAmountInsighter, GreatestAmountOfDaysTalkingInsighter, \
    LongestConversationInsighter, TopMessagesAmountInsighter, GreatestPhotoAmountInsighter
from libs.contacts import ContactManager
from libs.messages import MessageManager


print('Loading database...')
contact_manager = ContactManager.from_wa_db('wa.db')
message_manager = MessageManager.from_msgstore_db('msgstore.db')

insighter_manager = InsighterManager(contact_manager, group_by_name=True)
longest_audio_insighter = LongestAudioInsighter()
greatest_audio_insighter = GreatestAudioAmountInsighter()
greatest_amount_of_days_talking_insighter = GreatestAmountOfDaysTalkingInsighter()
greatest_photo_amount_insighter = GreatestPhotoAmountInsighter()
top_messages_amount_insighter = TopMessagesAmountInsighter()
longest_conversation_insighter = LongestConversationInsighter()
insighter_manager.add_insighter(longest_audio_insighter)
insighter_manager.add_insighter(greatest_audio_insighter)
insighter_manager.add_insighter(greatest_photo_amount_insighter)
insighter_manager.add_insighter(greatest_amount_of_days_talking_insighter)
insighter_manager.add_insighter(longest_conversation_insighter)
insighter_manager.add_insighter(top_messages_amount_insighter)

print('Applying insighters...')
for message in message_manager:
    insighter_manager.update(message)

print(longest_audio_insighter.winner)
print(greatest_audio_insighter.winner)
print(greatest_photo_amount_insighter.winner)
print(greatest_amount_of_days_talking_insighter.winner)
print(longest_conversation_insighter.winner)
print(top_messages_amount_insighter.winner)
