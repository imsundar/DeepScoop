# Web controller application which anchors asupmate 

# RAG TOOLs works as follows : 
# The RAG Setup: In S3 we have cluster logs saved based on cluster id. 
# We vectorise those logs and save them in faiss db. When the user queries 
# for information, we look up the faiss db for data related to user's cluster 
# and identify relevant chunks based on similarity search and provide that 
# to Bedrock, which uses the data to provide suggestions. 

from common import *
from persistence import *
from dataprocess import *
from webexIntegration import *
from AwsS3 import *
from redisHandler import *
from agent import *


# Flask app setup
app = Flask(__name__)
app.debug = False


# *************************************************************
# *************************************************************
# All possible App routes of controller
# *************************************************************
# *************************************************************

@app.route('/', methods=['POST'])
def handle_webex_message():    
    """Handle incoming WebEx messages."""  
    
    message_data = request.json
    # print(f"message data : {message_data}")          
    
    user_mail = retrieve_user_mail(message_data['data']['personId'])
    print(f"user_mail : {user_mail}")
    init_user(user_mail)      
        
    resource = message_data.get("resource")
    if resource == "attachmentActions":
        print("Handling an attachment action...")
        action_id = message_data['data']['id']
        action_response = get_attachment_action_response(action_id)
        # print(f"action_response {action_response}")
        if action_response:
            inputs = action_response['inputs']            
            user_action = inputs.get('action')            
            cluster_input = inputs.get('cluster_input')      

            if user_action == "set_cluster_uuid":                                               
                set_cluster_id(user_mail, cluster_input)                       
                send_message(f"Cluster ID set to {cluster_input}", user_mail)
            elif user_action == "vectorize_cluster":
                update_status = update_vectors(cluster_input)
                send_message(update_status, user_mail)

        return jsonify({'status': 'Attachment action processed'}), 200   
    elif resource == "messages":
        print("Handling a message...")    

    message_id = message_data['data']['id']

    # Check if the message has already been processed
    if message_id in processed_message_ids:
        print("already processed message id being sent")
        return jsonify({'status': 'Message already processed'}), 200
    
    processed_message_ids.add(message_id)  
      
    message = retrieve_message(message_id)

    if message is None:
        return jsonify({'status': 'No message found'}), 200

    user_question = message['text']
    print(f"Received question: {user_question}")
    
    # Respond with options card if user types "options"
    if user_question.lower() == "options":
        card_content = {
            "type": "AdaptiveCard",
            "version": "1.2",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Please provide cluster uuid and choose an action:",
                    "weight": "Bolder",
                    "size": "Medium"
                },
                {
                    "type": "Input.Text",
                    "id": "cluster_input",
                    "placeholder": "Enter Cluster ID here"
                }                
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Vectorize Cluster Data",
                    "data": {"action": "vectorize_cluster"}
                },
                {
                    "type": "Action.Submit",
                    "title": "Set Cluster UUID",
                    "data": {"action": "set_cluster_uuid"}
                },
                {
                    "type": "Action.OpenUrl",
                    "title": "Upload standalone logs",
                    "url": "http://44.204.10.189:5000/upload"
                }
            ]
        }
        send_message_with_card(card_content, message['email'])
        return jsonify({'status': 'Options card sent'}), 200

    # Validate if cluster ID is set in session  
    user_info = get_user_info(user_mail)  
    print(f"user info fetched : {user_info}")   
    if not user_info or user_info['cluster_id'] == '':
        error_message = {"error": "Cluster ID not set. Use 'Options' to set cluster id to begin."}
        send_message(error_message['error'], message['email'])  # Send error back to WebEx
        return jsonify(error_message), 400    
    
    # Check if the vector store for the cluster ID exists
    vector_store[user_info['cluster_id']] = load_vector_store(user_info['cluster_id'])
    if vector_store[user_info['cluster_id']] is None: 
      error_message = {"error": f"No vector store found for cluster {user_info['cluster_id']}. Please update vectors for the data. Type 'options' "}
      send_message(error_message['error'], message['email'])  # Send error back to WebEx
      return jsonify(error_message), 400             

    # Get the response using the LLM and vector store
    response = get_agent_response(user_info['cluster_id'], user_question, user_mail)

    # Send the response back to the user via WebEx
    send_message(response, message['email'])

    return jsonify({'status': 'Message processed', 'answer': response}), 200


#endpoint to handle custom file uploads
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':        
        full_path = ''
        files = request.files.getlist('files')  # Get multiple files

        if not files or files[0].filename == '':
            return jsonify({"error": "No files selected"}), 400    
        
        for file in files:
            relative_path = file.filename  # This may include subfolder info
            full_path = os.path.join(UPLOAD_FOLDER, relative_path)
            full_path = os.path.normpath(full_path)  # Ensure correct slashes
            
            # Create necessary subdirectories before saving the file
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            file.save(full_path)  # Save file correctly        
            
        update_vectors(os.path.dirname(file.filename), True, True)        
        return jsonify({"message": "File uploaded & vectorised successfully", "uploaded to": full_path})

    return render_template('upload.html')  # Serve the HTML upload form


# Set the cluster ID in the session
@app.route('/set_cluster_id/<person_email>/<cluster_id>', methods=['GET'])
def set_cluster_id(person_email, cluster_id):
    """Update the cluster ID in Redis."""
    init_user(person_email)  # Ensure user exists
    update_data_in_redis(person_email, "cluster_id", cluster_id)
    print(f"Updated cluster ID for {person_email} in Redis")
    return jsonify({"message": f"Cluster ID set to {cluster_id}."}), 200

# Manually trigger vector update for a given cluster ID
def update_vectors(cluster_id, force=False, isUpload=False):
    """Download and vectorize documents for the given cluster ID."""
    # Check the path for the cluster
    cluster_path = os.path.join('data', cluster_id)
    uploads_path = os.path.join('uploads', cluster_id)
    # print(f"uploads path : {uploads_path} , cluster_id {cluster_id}")

    # Check if the files already exist
    if os.path.exists(cluster_path):
        if not force:
            # If files exist and force is not set, return the date of the files available
            modification_time = os.path.getmtime(cluster_path)
            return f"Files already present for {cluster_id}. Last updated: {time.ctime(modification_time)}"

    # If force is set or files don't exist, download and vectorize
    if not isUpload: download_files_from_s3(cluster_id)  # Function to download files from S3
    docs = data_ingestion(uploads_path if isUpload else cluster_path, cluster_id)  # Function to ingest data from the given path

    # Create or update the vector store for the cluster
    save_vector_store(docs, cluster_id)     
    
    return f"Vector store updated for cluster {cluster_id}."


@app.route('/update_vectors/<cluster_id>', methods=['GET'])
def update_vectors_endpoint(cluster_id):
    """Endpoint to update vector stores for a specific cluster."""    
    force = request.args.get('force', 'false').lower() == 'true'   

    update_status = update_vectors(cluster_id, force)
    return jsonify({"status": update_status}), 200

@app.route('/vscode/analyze', methods=['POST'])
def vsEditorHandler():
    data = request.json  # Get JSON body
    print("requst data: {data}")
    user_mail= data.get("usermail", "")    
    user_question = data.get("question", "")
    
    print(f"user_mail: {user_mail}")    
    print(f"Question: {user_question}")

    user_info = get_user_info(user_mail)      

    global vector_store
    
    vector_store[user_info['cluster_id']] = load_vector_store(user_info['cluster_id'])
    if vector_store[user_info['cluster_id']] is None:    
        error_message = {"error": f"No vector store found for cluster {user_info['cluster_id']}. Please update vectors for the data using 'options' in webex"}            
        return jsonify(error_message), 400    

    # Get the response using the LLM and vector store
    response = get_agent_response(user_info['cluster_id'], user_question, user_mail)        

    return jsonify({'status': 'Message processed', 'answer': response}), 200    

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# init_webhook is not needed everytime the server is restarted. 
# I have already tested the webhooks and they are proper in place for now. 
# when need to create new webhooks and flush older ones we can run the init_webhook

if __name__ == '__main__':            
    # init_webhook()    
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(port=8000, debug=False)
