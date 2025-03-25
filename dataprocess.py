from common import *

## Data ingestion
from PyPDF2 import PdfReader
from common import *

## Data ingestion
import pdfplumber


def data_ingestion(directory_path, cluster_id):
    """
    Ingest documents from the given directory and add them to the BM25 index for the specified cluster.
    Supports both .log and .pdf files.
    """
    documents = []
    text_splitter = RecursiveCharacterTextSplitter(separators=["\n\n", "\n", " ", ""], chunk_size=500, chunk_overlap=50)

    # Ensure that the BM25 index for the cluster is initialized
    # if cluster_id not in bm25_indices or bm25_indices[cluster_id] is None:
    #     bm25_indices[cluster_id] = BM25Index()  # Initialize the BM25 index for this cluster

    # Function to process .log files
    def process_log_file(file_path):
        with open(file_path, 'r', encoding='utf-8') as log_file:
            content = log_file.read()
        split_docs = text_splitter.split_text(content)
        return [Document(page_content=chunk, metadata={"file_path": file_path}) for chunk in split_docs]

    # Function to process .pdf files
    def process_pdf_file(file_path):
        content = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:  # Only append text if it's not empty
                        content += page_text
                    else:
                        print(f"Warning: No text extracted from page in {file_path}")
        except Exception as e:
            print(f"Error processing PDF file {file_path}: {e}")
            return []  # Return an empty list if there's an error

        if not content.strip():  # Check if the extracted text is empty
            print(f"Warning: No extractable text found in {file_path}")
            return []  # If no text was extracted, return an empty list

        split_docs = text_splitter.split_text(content)
        return [Document(page_content=chunk, metadata={"file_path": file_path}) for chunk in split_docs]

    # Collect all .log and .pdf files from the directory
    file_paths = []
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".log") or file.endswith(".pdf"):
                file_paths.append(os.path.join(root, file))

    # Function to process files based on their extension
    def process_file(file_path):
        if file_path.endswith(".log"):
            return process_log_file(file_path)
        elif file_path.endswith(".pdf"):
            return process_pdf_file(file_path)
        return []

    # Process files in parallel to speed up the ingestion
    with ThreadPoolExecutor(max_workers=4) as executor:  # Adjust max_workers
        results = list(executor.map(process_file, file_paths))

    # Flatten results and add them to the BM25 index for the cluster
    for result in results:
        documents.extend(result)
    #     # Ensure we use the existing bm25_indices[cluster_id] to add documents
    #     bm25_indices[cluster_id].add_documents([doc.page_content for doc in result], cluster_id)

    print(f"data ingestion done with {len(documents)} documents")
    return documents

def process_documents_in_batches(docs, batch_size=500):
    all_processed_docs = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Split docs into batches
        batches = [docs[i:i + batch_size] for i in range(0, len(docs), batch_size)]
        
        # Submit each batch for processing
        futures = [executor.submit(process_batch, batch) for batch in batches]
        
        # Collect all results from batches
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            all_processed_docs.extend(result)
    
    return all_processed_docs

# Function to process each batch (currently a placeholder, can be customized)
def process_batch(batch):
    # You can perform any custom processing on each batch here if needed
    # For now, just returning the batch itself
    for doc in batch:
        doc.metadata = {"cluster_id": doc.metadata.get("cluster_id", "")}  # Ensure metadata is set
    return batch

# Function to update the vector store and BM25 index using multi-threading
def save_vector_store(docs, cluster_id):
    # Process documents in parallel using multi-threading
    processed_docs = process_documents_in_batches(docs)
    
    # Initialize FAISS vector store with processed documents    
    vectorstore_faiss = FAISS.from_documents(processed_docs, bedrock_embeddings)

    # Directory to save the FAISS index
    save_directory = "faiss_index"
    os.makedirs(save_directory, exist_ok=True)
    
    # Save the FAISS vector store locally
    vectorstore_faiss.save_local(os.path.join(save_directory, f"faiss_index_{cluster_id}"))

    # Update BM25 index
    # bm25_documents = [doc.page_content for doc in processed_docs]
    # bm25_index.add_documents(bm25_documents, cluster_id)
    # bm25_indices[cluster_id] = bm25_index
    # print(f"BM25 index updated for cluster {cluster_id}")
    