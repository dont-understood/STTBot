# External
import sqlite3
import os
import json

# Internal
from STTBot.utils import env

# Global variables
db = env.get_cfg("PATH_DB")
insert_batch_size = 10000
data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
required_fields = ["ts", "user", "text"]
insert_sql = "INSERT or IGNORE INTO messages (timestamp, channel_id, channel_name, user_id, user_name, message, permalink) VALUES (:timestamp, :channel_id, :channel_name, :user_id, :user_name, :message, :permalink)"
permalink_base_url = "https://sweaty-tikitaka.slack.com/archives"

# Global accessors
con = sqlite3.connect(db, isolation_level=None)


def main():
    channel_dirs = [d.name for d in os.scandir(data_path) if d.is_dir()]
    channel_info = get_json_from_file(os.path.join(data_path, "channels.json"))

    for channel_dir in [os.path.join(data_path, channel_dir) for channel_dir in channel_dirs]:
        channel_name = os.path.basename(channel_dir)
        channel_id = [channel['id'] for channel in channel_info if channel['name'] == channel_name][0]
        env.log.info(f"Getting messages for {channel_name}")

        message_data = []
        for message_file in os.scandir(channel_dir):
            message_data.extend(process_message_file(message_file, channel_id))

        for message in message_data:
            message['channel_id'] = channel_id
            message['channel_name'] = channel_name

        env.log.info(f"Found {len(message_data)} messages for {channel_name}")
        insert_messages(message_data)
        env.log.info(f"Inserted/updated {len(message_data)} messages for {channel_name}")


def insert_messages(message_data):
    message_data = [message_data[i * insert_batch_size:(i + 1) * insert_batch_size] for i in range((len(message_data) + insert_batch_size - 1) // insert_batch_size)]
    for (i, batch) in enumerate(message_data):
        env.log.info(f"Inserting batch {i + 1} of {len(message_data)} to the database")
        con.executemany(insert_sql, batch)


def process_message_file(filepath, channel_id):
    message_file_json = get_json_from_file(filepath)

    message_data = []
    for message in message_file_json:
        message = resolve_missing_keys(message)
        if message is None:
            continue

        permalink = f"{permalink_base_url}/{channel_id}/p{message['ts'].replace('.', '')}"
        message = {'timestamp': message['ts'], 'user_id': message['user'], 'user_name': message['user_profile']['name'], 'message': message['text'], 'permalink': permalink}
        message_data.append(message)

    return message_data


def resolve_missing_keys(message):
    missing_keys = [key for key in required_fields if key not in message.keys()]

    if len(missing_keys) > 0:
        env.log.debug(f"Message with timestamp {message['ts']} missing required fields: {','.join(missing_keys)}")
        return None

    if 'user_profile' not in message.keys():
        message['user_profile'] = {'name': 'Unknown'}

    return message


def get_json_from_file(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)


if __name__ == "__main__":
    main()
    con.close()
