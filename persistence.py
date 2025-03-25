from common import *


# *************************************************************
# #util functions for loading vector stores from persistence
# def load_all_vector_stores():
#     global vector_stores
    
#     faiss_index_dir = "faiss_index"
#     faiss_files = glob.glob(os.path.join(faiss_index_dir, "faiss_index_*"))

#     for faiss_file in faiss_files:
#         cluster_id = os.path.basename(faiss_file).split('_')[-1]

#         try:  
#             vector_store = FAISS.load_local(faiss_file, bedrock_embeddings, allow_dangerous_deserialization=True)
#             vector_stores[cluster_id] = vector_store 
#         except Exception as e:
#              print(f"Failed to load vector store from {faiss_file}: {str(e)}")

#     print(f"Loaded {len(vector_stores)} vector stores into memory.")

def load_vector_store(cluster_id):
    """
    Load a specific vector store based on the provided cluster ID.
    """
    global vector_store

    faiss_index_dir = "faiss_index"
    faiss_file = os.path.join(faiss_index_dir, f"faiss_index_{cluster_id}")

    if not os.path.exists(faiss_file):
        print(f"Vector store for cluster {cluster_id} not found.")
        return None

    try:
        vector_store[cluster_id] = FAISS.load_local(faiss_file, bedrock_embeddings, allow_dangerous_deserialization=True)
        # vector_stores[cluster_id] = vector_store
        print(f"Loaded vector store for cluster {cluster_id}.")
        return vector_store[cluster_id]
    except Exception as e:
        print(f"Failed to load vector store for {cluster_id}: {str(e)}")
        return None

# def load_all_bm25_indices():
#     """
#     Load all BM25 indices saved in the 'bm25_index' directory.
#     """
#     global bm25_indices
#     bm25_index_dir = "bm25_index"

#     if not os.path.exists(bm25_index_dir):
#         print("No BM25 indices found.")
#         return

#     for filename in os.listdir(bm25_index_dir):
#         if filename.endswith(".pkl"):
#             cluster_id = filename.split("_")[-1].replace(".pkl", "")
#             try:
#                 # Load the BM25 index for this cluster and store it in bm25_indices
#                 bm25_indices[cluster_id] = BM25Index()  # Initialize BM25Index object
#                 bm25_indices[cluster_id].load_cluster_index(cluster_id)
#             except Exception as e:
#                 print(f"Failed to load BM25 index for cluster {cluster_id}: {str(e)}")

#     print(f"Loaded {len(bm25_indices)} BM25 indices.")