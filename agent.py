import os
from langchain.tools import Tool
from langchain_google_vertexai import VertexAI
from langchain.agents import initialize_agent, AgentType
from google.auth import load_credentials_from_file

agentfile_user_cluster_id = ""
agentfile_user_query = ""
agentfile_user_email = ""


# Set up Google Cloud authentication
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\sundar\OneDrive\Documents\ai\test2\agent1-453416-68c2001b062a.json"

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
    retriever = vector_store[cluster_id].as_retriever(
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
    user_info = get_user_info(user_mail)
    prompt = PROMPT.format(context=combined_context, question=query, summary=user_info['memory'])      
    
    print(f"Conversation summary : {user_info['memory']}")   

    llm_conversation = ConversationChain(llm=get_claude_llm(), memory=get_memory(), verbose=True)

    # Step 5: Generate Response Using LLM
    chat_reply = llm_conversation.invoke(prompt)

    # persist conversation summary in redis    
    update_data_in_redis(user_mail, "memory", llm_conversation.memory.buffer)

    # Step 6: Prefix Cluster ID to the Final Response
    response = f"CID: {cluster_id} - {chat_reply['response']}"
    print(response)
    return response

log_rag_tool = Tool(
    name="AnalyseClusterLog",
    func=analyse_cluster_log,
    description="Analyses storage cluster logs for user queries and responds"
)

# Define a simple tool
# def get_word_length(word: str) -> str:
#     """Returns the length of a word as a string."""
#     return f"The word '{word}' has {len(word)} letters."

# word_length_tool = Tool(
#     name="GetWordLength",
#     func=get_word_length,
#     description="Returns the length of a word."
# )

# Initialize Gemini Pro model via Vertex AI
llm = VertexAI(
    model_name="gemini-1.5-pro",
    temperature=0.1, 
    max_output_tokens=8000, 
    top_p = 0.9
)

# Use ZERO_SHOT_REACT_DESCRIPTION for agent
tools = [log_rag_tool]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
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
    When the user asks questions on the logs, use the log_rag_tool and pass in the query. It will help you fetch the relevant logs from FAISS 
    and also will analyse the FAISS results for the query asked. Finally it responds with its analysis. Before sending the analysis to user, 
    if you have any valid further questions, you can ask the same to the log_rag_tool and get it clarified and then send the final response to 
    user.  

    user question: {question}

    Your output should be a clear and concise response to the user question.    
    """  

    PROMPT = PromptTemplate(template=prompt_template, input_variables=["question"]) 
    prompt = PROMPT.format(question=query)         


    response = agent.invoke({"input": prompt}) 
    response = f"CID: {cluster_id} - {response}"