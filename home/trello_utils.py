#trello_utils.py
import requests
from django.conf import settings


TRELLO_API_BASE = 'https://api.trello.com/1'
BOARD_ID = settings.TRELLO_BOARD_ID
API_KEY = settings.TRELLO_API_KEY
TOKEN = settings.TRELLO_API_TOKEN
LIST_ID = '67d0065d01438695cdc2430a'


def get_board_members():
    url = f'{TRELLO_API_BASE}/boards/{BOARD_ID}/members'
    params = {'key': API_KEY, 'token': TOKEN}
    response = requests.get(url, params=params)
    return response.json()

DONE_LIST_ID = '67d0065d01438695cdc2430c'  # ✅ Replace with your real Done list ID

def create_or_update_card(card_id=None, name='', desc='', due=None, member_ids=[], completed=False):  # ✅ updated
    if card_id:
        url = f"{TRELLO_API_BASE}/cards/{card_id}"
        method = requests.put
    else:
        url = f"{TRELLO_API_BASE}/cards"
        method = requests.post

    list_id = DONE_LIST_ID if completed else LIST_ID  # ✅ NEW conditional logic

    data = {
        'key': API_KEY,
        'token': TOKEN,
        'name': name,
        'desc': desc,
        'idMembers': ','.join(member_ids),
        'idList': list_id,
    }

    # ✅ Only include 'due' if not None or empty
    if due:
        data['due'] = due

    response = method(url, data=data)

    print("Status Code:", response.status_code)
    print("Response Text:", response.text)

    try:
        return response.json()
    except Exception as e:
        raise Exception(f"Trello API returned non-JSON: {response.text}")


def delete_card(card_id):
    url = f"{TRELLO_API_BASE}/cards/{card_id}"
    params = {'key': API_KEY, 'token': TOKEN}
    response = requests.delete(url, params=params)
    
    # Logging for debugging
    print("Delete Status Code:", response.status_code)
    print("Delete Response:", response.text)

    return response.status_code == 200
