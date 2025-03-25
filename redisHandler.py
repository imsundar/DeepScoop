from common import *
import faiss 
import base64
import io
import tempfile
import pickle
from langchain.memory import ConversationSummaryBufferMemory

# Redis code to handle user_info ds memory in prod env
def init_user(user_mail):
    """Initialize user data in Redis if not already set."""
    if not redis_client.exists(user_mail):  # Check if user data exists
        user_info = {
            'cluster_id': '',
            'memory': '',             
        }
        redis_client.set(user_mail, json.dumps(user_info))  # Store user data as JSON
        print(f"Initialized user {user_mail} in Redis")
    else: 
        print("User info already existing in redis.")

def get_user_info(user_mail):
    """Retrieve user data from Redis."""
    user_info = redis_client.get(user_mail)
    if user_info:
        print("successfully fetched user info from redis")
        return json.loads(user_info)  # Convert JSON string back to dictionary
    return None

def update_data_in_redis(user_mail, dataType, data):
    user_info = get_user_info(user_mail)
    if user_info:
        match dataType:
            case "memory":
                user_info['memory'] = data
            case "cluster_id":
                user_info['cluster_id'] = data
                user_info['memory'] = None

        redis_client.set(user_mail, json.dumps(user_info))  # Save back to Redis
        print(f"Successfully updated data in Redis for user: {user_mail}")

