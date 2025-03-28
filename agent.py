import os
from langchain.tools import Tool
from langchain_google_vertexai import VertexAI
from langchain.agents import initialize_agent, AgentType
from google.auth import load_credentials_from_file
from langchain.prompts import PromptTemplate
from redisHandler import *
from persistence import *
from langchain.chains import ConversationChain
from langchain.memory import ConversationSummaryBufferMemory
import requests

agentfile_user_cluster_id = ""
agentfile_user_query = ""
agentfile_user_email = ""


# Set up Google Cloud authentication
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"agent1-453416-68c2001b062a.json"

# Initialize Gemini Pro model via Vertex AI
# gemini-1.5-pro
llm = VertexAI(
    model_name="gemini-2.0-flash-001",
    temperature=0.1, 
    max_output_tokens=8000, 
    top_p = 0.9
)

# Create memory using ConversationSummaryBufferMemory
def get_memory():    
    memory = ConversationSummaryBufferMemory(llm=llm, max_token_limit=300)
    return memory

# Define the PromptTemplate for the conversation
prompt_template = """
Human: you are helping the development team of the Hyperconverged Infrastructure storage cluster product. The data given
to you are the application logs of hyperflex clusters or documents related to hyperflex. Try to answer developers' queries
based on the context and logs. Pinpoint the issues related to the question asked and provide suggestions to resolve it.
The user can also ask to explain programming exceptions captured on logs or ask explanation of code snippet for which
use your knowledge on the corresponding programming language and help the user with the questions.
Try to maintain the chat context and stay relevant to the conversation history.
<context>
{context}
</context>

Question: {question}

Conversation Summary so far to aid in context: {summary}

Assistant:
"""

PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])

def analyse_cluster_log(query):
    """
    Retrieve relevant log context from FAISS for the user query. Sends the context and query to 
    LLM for analysing and returns the response. 
    """
    
    # Step 1: FAISS Search      
    retriever = vector_store[agentfile_user_cluster_id].as_retriever(
        search_type="similarity", search_kwargs={"k": 5}
    )
    faiss_results = retriever.get_relevant_documents(query)  

    # Step 3: Combine Results (Avoiding Duplicates)
    combined_results = set()
    # bm25_fetch = set()

    for doc in faiss_results:
        combined_results.add(doc.page_content)    

    # Step 4: Prepare Combined Context
    combined_context = "\n".join(combined_results)    
    user_info = get_user_info(agentfile_user_email)
    prompt = PROMPT.format(context=combined_context, question=query, summary=user_info['memory'])      
    
    print(f"Conversation summary : {user_info['memory']}")   

    llm_conversation = ConversationChain(llm=llm, memory=get_memory(), verbose=True)

    # Step 5: Generate Response Using LLM
    chat_reply = llm_conversation.invoke(prompt)

    # persist conversation summary in redis    
    update_data_in_redis(agentfile_user_email, "memory", llm_conversation.memory.buffer)

    # Step 6: Prefix Cluster ID to the Final Response
    response = f"CID: {agentfile_user_cluster_id} - {chat_reply['response']}"
    print(response)
    return response

log_rag_tool = Tool(
    name="AnalyseClusterLog",
    func=analyse_cluster_log,
    description="Analyses storage cluster logs for user queries and responds"
)


kb_prompt_template = """
Human: you are helping the development team of the Hyperconverged Infrastructure storage cluster product. The data given
to you are the internal knowledge base data of hyperflex clusters or documents related to hyperflex. Based on the user query, use the 
context data given and help them with appropriate workaround or solution.Try to maintain the chat context and stay relevant to the conversation history.
<context>
{context}
</context>

Question: {question}

Conversation Summary so far to aid in context: {summary}

Assistant:
"""

KB_PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])

def fetch_knowledge_base_data(query):
    """
    Fetches relevant internal knowledge base content and suggestions from FAISS for the user query. Sends the context and query to 
    LLM for analysing and returns the response. 
    """
    
    # Step 1: FAISS Search     
    # in expansion of the solution, to select the kb name we might need another agent / separate tool 
    # for now every knowledge base will be put under the FAISS name "cluster" 

    kb_vector_store["cluster"] = load_kb_vector_store("cluster")

    retriever = kb_vector_store["cluster"].as_retriever(
        search_type="similarity", search_kwargs={"k": 5}
    )
    faiss_results = retriever.get_relevant_documents(query)  

    # Step 3: Combine Results (Avoiding Duplicates)
    combined_results = set()
    # bm25_fetch = set()

    for doc in faiss_results:
        combined_results.add(doc.page_content)    

    # Step 4: Prepare Combined Context
    combined_context = "\n".join(combined_results)    
    user_info = get_user_info(agentfile_user_email)
    prompt = KB_PROMPT.format(context=combined_context, question=query, summary=user_info['memory'])      
    
    print(f"Conversation summary : {user_info['memory']}")   

    llm_conversation = ConversationChain(llm=llm, memory=get_memory(), verbose=True)

    # Step 5: Generate Response Using LLM
    chat_reply = llm_conversation.invoke(prompt)

    # persist conversation summary in redis    
    update_data_in_redis(agentfile_user_email, "memory", llm_conversation.memory.buffer)

    # Step 6: Prefix Cluster ID to the Final Response
    response = f"CID: {agentfile_user_cluster_id} - {chat_reply['response']}"
    print(response)
    return response


knowledge_base_rag_tool = Tool(
    name="FetchKnowledgeBaseData",
    func=fetch_knowledge_base_data,
    description="Analyses internal knowledge bsae of Hyperflex clusters for user queries and responds"
)

def run_commands_on_cluster(command):
    """
    Runs user requested commands on hyperflex cluster through rest api calls. 
    """
    base_url = "http://54.159.154.158:5000"
    url = f"{base_url}/cluster/{agentfile_user_cluster_id}/{command}"

    response = requests.put(url)

    print("Status Code:", response.status_code)
    print("Response:", response.text)
    
    return response.text 
    

cluster_action_tool = Tool(
    name="RunCommandsOnCluster",
    func=run_commands_on_cluster,
    description="Runs user requested commands on hyperflex clusters"
)

# Use ZERO_SHOT_REACT_DESCRIPTION for agent
tools = [log_rag_tool, knowledge_base_rag_tool, cluster_action_tool]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True
)

def get_agent_response(cluster_id, query, user_mail):
    global agentfile_user_cluster_id     
    global agentfile_user_email 
    global agentfile_user_query 

    agentfile_user_cluster_id = cluster_id 
    agentfile_user_email = user_mail 
    agentfile_user_query = query 

    prompt_template = """
    you are helping the development team of the Hyperconverged Infrastructure storage cluster product. The data given
    to you are the application logs of hyperflex clusters or documents related to hyperflex. Try to answer developers' queries
    based on the context and logs. 

    Your process: 
    Major task : When the user asks questions on the logs, use the log_rag_tool and pass in the query. It will help you fetch the relevant logs from FAISS 
    and also will analyse the FAISS results for the query asked. Finally it responds with its analysis. Before sending the analysis to user, 
    if you have any valid further questions, you can ask the same to the log_rag_tool and get it clarified and then send the final response to 
    user. Use the same log_rag_tool if the question is related to any programming language based queries.  

    Additional task 1 : Once the user is satisfied with understanding the issue from the logs, they might want to 
    check if there are some data available on the existing knowledge base for a solution or workaround. In that case use knowledge_base_rag_tool and send the user query. 
    The tool will fetch relevant data from knowledge base and also analyse the data. Use the tool and send the response to the user. If there are no relevant data available 
    on the knowledge base, let the user know that. 

    Additional task 2 : If the user wants to run commands on the cluster only then use the cluster_action_tool. 
    Inputs you can send to this tool : 
    1) if user wants to add additional node to the cluster call the cluster_action_tool with "nodeadd" as input 
    2) if the user wants to check status of the cluster call the cluster_action_tool with "status" as input 
    3) if the user wants to update health of the cluster then call the cluster_action_tool with "updatehealth" as input 
    Always return response of cluster_action_tool in format that each result field placed in a new line. 

    Note: If the users question is out of context of Hyperflex clusters and not in one of application log analysis, programming based exception queries, Knowledge based data questions, 
    running commands in hyperflex cluster then let them know you are designed to help with hyperflex related questions and log analysis. Inform them this in a humourous way.      

    Your output should be based on the tools response for the user query. 
    """  

    PROMPT = PromptTemplate(template=prompt_template, input_variables=["question"]) 
    prompt = PROMPT.format(question=query)         


    response = agent.invoke({"input": prompt}) 
    output = response['output']    
    response = f"CID: {cluster_id} - {output}"
    return response 