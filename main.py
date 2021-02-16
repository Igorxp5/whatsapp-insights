from libs.insighters import InsighterManager, LongestAudioInsighter, \
    GreatestAudioAmountInsighter, GreatestAmountOfDaysTalkingInsighter, \
    LongestConversationInsighter, TopMessagesAmountInsighter, \
    GreatestPhotoAmountInsighter, LongestCallInsighter, \
    GreatestCallAmountInsighter, LongestTimeInCallsInsighter
from libs.contacts import ContactManager
from libs.messages import MessageManager
from libs.calls import CallManager


print('Loading database...')
contact_manager = ContactManager.from_wa_db('wa.db')
call_manager = CallManager.from_msgstore_db('msgstore.db')
message_manager = MessageManager.from_msgstore_db('msgstore.db')

insighter_manager = InsighterManager(contact_manager=contact_manager, 
                                     group_by_name=True)

insighters = [
    LongestAudioInsighter, GreatestAudioAmountInsighter,
    GreatestAmountOfDaysTalkingInsighter, GreatestPhotoAmountInsighter,
    TopMessagesAmountInsighter, LongestConversationInsighter,
    LongestCallInsighter, GreatestCallAmountInsighter, LongestTimeInCallsInsighter
]

for insighter in insighters:
    insighter_manager.add_insighter(insighter())

print('Applying insighters in the messages...')
for message in message_manager:
    insighter_manager.update(message)

print('Applying insighters in the calls...')
for call in call_manager:
    insighter_manager.update(call)

print('\nResults:')

for insighter in insighter_manager.insighters:
    print(f'# {insighter.title}')
    winner = insighter.winner
    if not isinstance(winner, list):
        winner = [winner]
    for w in winner:
        print(f'Contact: {w.jid}')
        print(f'Message: {w.data}')
        print(f'Value: {w.value}\n')
