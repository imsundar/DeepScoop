from common import *


def retrieve_message(message_id):    
    """Retrieve message details from WebEx API."""
    headers = {
        'Authorization': f'Bearer {WEBEX_ACCESS_TOKEN}'
    }
    url = f'https://api.ciscospark.com/v1/messages/{message_id}'
    response = requests.get(url, headers=headers)

    # print(f"check the response of message here : {response.text}")

    if response.status_code == 200:
        message_data = response.json()        
        person_email = message_data.get('personEmail', '')
        message_text = message_data.get('text', '')

        if 'webex.bot' not in person_email:
            return {'text': message_text, 'email': person_email}
    
    return None

def retrieve_user_mail(person_id):
    # print(f"person id {person_id}")
    url = f'https://api.ciscospark.com/v1/people/{person_id}'
    headers = {
        'Authorization': f'Bearer {WEBEX_ACCESS_TOKEN}',
    }

    response = requests.get(url, headers=headers)
    # print(f"user information retrieval response: {response.text}")

    if response.status_code == 200:
        person_data = response.json()
        return person_data['emails'][0]  # Assuming the user has one email
    
    return None

def send_message(text, person_email):
    """Send message to a specific person on WebEx."""
    headers = {
        'Authorization': f'Bearer {WEBEX_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    url = 'https://api.ciscospark.com/v1/messages'
    payload = {
        'toPersonEmail': person_email,
        'text': text
    }

    requests.post(url, headers=headers, json=payload)

def send_message_with_card(card_content, person_email):
    """Send a message with an Adaptive Card to a user on WebEx."""
    headers = {
        'Authorization': f'Bearer {WEBEX_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    url = 'https://api.ciscospark.com/v1/messages'
    payload = {
        'toPersonEmail': person_email,
        'markdown': "Please select an option and provide input:",
        'attachments': [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_content
            }
        ]
    }
    response = requests.post(url, headers=headers, json=payload)   

# *************************************************************
#Webex hook routing code 

def init_webhook():
    """Register webhook with WebEx."""
    # delete_existing_webhooks()
    register_webhook()
    print("status: 'Webhook registered successfully")

def register_webhook():
    """Register webhooks for message and attachment actions events."""
    headers = {
        'Authorization': f'Bearer {WEBEX_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    url = 'https://api.ciscospark.com/v1/webhooks'

    # Register webhook for messages
    message_payload = {
        'name': 'webex_bot_message_webhook',
        'targetUrl': TARGET_URL,
        'resource': 'messages',
        'event': 'created'
    }
    response = requests.post(url, headers=headers, json=message_payload)
    if response.status_code == 200:
        print("Webhook for messages registered successfully.")
    else:
        print(f"Failed to register messages webhook: {response.text}")

    # Register webhook for attachment actions
    attachment_payload = {
        'name': 'webex_bot_attachment_webhook',
        'targetUrl': TARGET_URL,
        'resource': 'attachmentActions',
        'event': 'created'
    }
    response = requests.post(url, headers=headers, json=attachment_payload)
    if response.status_code == 200:
        print("Webhook for attachment actions registered successfully.")
    else:
        print(f"Failed to register attachment webhook: {response.text}")

def delete_existing_webhooks():
    """Delete existing webhooks."""
    headers = {'Authorization': f'Bearer {WEBEX_ACCESS_TOKEN}'}
    response = requests.get('https://api.ciscospark.com/v1/webhooks', headers=headers)
    if response.status_code == 200:
        webhooks = response.json().get('items', [])
        for webhook in webhooks:
            print (f"webhooks data : {webhook}") 
            delete_webhook(webhook['id'])

def delete_webhook(webhook_id):
    """Delete a specific webhook by its ID."""
    headers = {'Authorization': f'Bearer {WEBEX_ACCESS_TOKEN}'}
    requests.delete(f'https://api.ciscospark.com/v1/webhooks/{webhook_id}', headers=headers)

def get_attachment_action_response(action_id):
    """Retrieve response from an Adaptive Card submission."""
    headers = {
        'Authorization': f'Bearer {WEBEX_ACCESS_TOKEN}'
    }
    url = f'https://api.ciscospark.com/v1/attachment/actions/{action_id}'
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # print(f"response : {response.text}")
        return response.json()
    else:
        print(f"Failed to retrieve attachment action: {response.text}")
        return None