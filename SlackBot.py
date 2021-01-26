import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import string
from datetime import datetime, timedelta
from WelcomeMessage import WelcomeMessage

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)
# Port to my Channel in SLACK
CHANNEL = 'C01GS8D2NG5'
app = Flask(__name__)

slack_event_adapter = SlackEventAdapter(
    os.environ['SIGNING_SECRET'], '/slack/events', app)

# Storing TOKEN
client = slack.WebClient(token=os.environ['SLACK_API_TOKEN'])


now = datetime.now()
current_time = now.strftime("%H:%M:%S")

# Call a specific end point and return the id of the BOT
BOT_ID = client.api_call("auth.test")['user_id']

welcome_messages = {}
# When sending private msg in SLACK it will ignore a BAD_WORDS
BAD_WORDS = ['bad', 'no', 'pythonnotgood']


SCHEDULTED_MESSAGES = [
    # edit channel key with your own channel id
    {'text': 'Current Time(Every hour)' + current_time, 'post_at': (
        datetime.now() + timedelta(hours=1)).timestamp(), 'channel': CHANNEL}
]


def send_welcome_message(channel, user):
    if channel not in welcome_messages:
        welcome_messages[channel] = {}
    if user in welcome_messages[channel]:
        return

    welcome = WelcomeMessage(channel, user)
    message = welcome.get_message()
    response = client.chat_postMessage(**message)
    welcome.timestamp = response['ts']
    welcome_messages[channel][user] = welcome


def list_scheduled_messages(channel):
    response = client.chat_scheduledMessages_list(channel=channel)
    messages = response.data.get('scheduled_messages')
    ids = []
    for msg in messages:
        ids.append(msg.get('id'))
    return ids


def schedule_messages(messages):
    ids = []
    for msg in messages:
        response = client.chat_scheduleMessage(
            channel=msg['channel'], text=msg['text'], post_at=msg['post_at']).data
        id_ = response.get('scheduled_message_id')
        ids.append(id_)
    return ids


def delete_scheduled_messages(ids, channel):
    for _id in ids:
        try:
            client.chat_deleteScheduledMessage(
                channel=channel, scheduled_message_id=_id)
        except Exception as e:
            print(e)


def check_if_bad_words(message):
    msg = message.lower()
    msg.translate(str.maketrans('', '', string.punctuation))
    return any(word in msg for word in BAD_WORDS)


@ slack_event_adapter.on('message')
def message(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    if user_id != None and BOT_ID != user_id:
        if text.lower() == 'start':
            send_welcome_message({user_id}, user_id)

        elif check_if_bad_words(text):
            # ts =event from duplicate msg's
            ts = event.get('ts')
            client.chat_postMessage(
                channel=channel_id, thread_ts=ts, text="This is a bad word")


# Adding a reaction to a msg sent into slack
@ slack_event_adapter.on('reaction_added')
def reaction(payload):
    event = payload.get('event', {})
    channel_id = event.get('item', {}).get('channel')
    user_id = event.get('user')
    if ({user_id}) not in welcome_messages:
        return
    welcome = welcome_messages[{user_id}][user_id]
    welcome.completed = True
    welcome.channel = channel_id
    message = welcome.get_message()
    updated_message = client.chat_update(**message)
    welcome.timestamp = updated_message['ts']

# Commands for SLACK


@ app.route('/new-content', methods=['POST'])
def new_content(payload):
    event = payload.get('event', {})
    data = request.form
    data.append(event)
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    client.chat_postMessage(
        channel=channel_id, text="New Tweets : {data}")
    return Response(), 200


@ app.route('/now', methods=['POST'])
def command_now():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    client.chat_postMessage(
        channel=channel_id, text="Current time: {current_time}")
    return Response(), 200


if __name__ == "__main__":
    schedule_messages(SCHEDULTED_MESSAGES)
    ids = list_scheduled_messages(CHANNEL)
    delete_scheduled_messages(ids, CHANNEL)
    # Auto update the web server we dont need to rerun the script
    app.run(debug=True)
