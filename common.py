from flask import Flask, request, jsonify, session
from flask_session import Session 
import json
import os
import boto3
import requests
import redis
import secrets
import datetime
import time
import glob
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from langchain_aws import BedrockEmbeddings
from langchain_community.llms import Bedrock
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain.schema import Document
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from flask import render_template

# Initializing BM25 Index globally
# bm25_indices = {}
# bm25_index = BM25Index(index_dir="bm25_index")

# in memory faiss store
vector_store = {}
kb_vector_store = {}

# shifted to redis
# user information mimicking session 
# user_info = {}

UPLOAD_FOLDER = "uploads"

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# WebEx bot details
WEBEX_ACCESS_TOKEN = 'N2RkYmZhMzAtM2NjMi00N2RlLWE5M2UtYWQ1YTgxMWQ0OWUzMWU1MDkxZWEtOTMy_PF84_1eb65fdf-9643-417f-9974-ad72cae0e10f'
TARGET_URL = 'http://44.204.10.189:5000'
# TARGET_URL = 'https://f935-2405-201-e008-e16b-7593-d5a8-1b8a-4661.ngrok-free.app'
processed_message_ids = set()

## Bedrock Clients
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
bedrock_embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v1", client=bedrock)