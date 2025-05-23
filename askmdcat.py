# -*- coding: utf-8 -*-
"""Untitled2.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/12cLPVQr5ICxr6NYD35EcFdbkJwdyNqCE
"""

import streamlit as st
import pandas as pd
import requests
from io import BytesIO, StringIO
from docx import Document
import os

# URLs to your raw GitHub files
STS_CSV_URL = "https://raw.githubusercontent.com/your-username/your-repo/main/mdcat_queries.csv"
PAST_PAPERS_DOCX_URL = "https://raw.githubusercontent.com/your-username/your-repo/main/past_tests.docx"

# Hugging Face API Info
GENERATOR_API_URL = "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta"
RETRIEVER_API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-base"
HF_API_KEY = st.secrets["HF_API_KEY"]

headers = {
    "Authorization": f"Bearer {HF_API_KEY}",
    "Content-Type": "application/json"
}

# Load STS CSV from GitHub
@st.cache_data
def load_sts_from_url(url):
    response = requests.get(url)
    return pd.read_csv(StringIO(response.text), encoding='latin-1')

# Load DOCX past paper from GitHub
@st.cache_data
def load_past_paper_from_url(url):
    response = requests.get(url)
    doc = Document(BytesIO(response.content))
    qa_pairs = []
    table = doc.tables[0]
    rows = [cell.text.strip() for row in table.rows for cell in row.cells if cell.text.strip()]
    for i in range(0, len(rows), 2):
        question = rows[i]
        answer = rows[i+1] if i+1 < len(rows) else ''
        qa_pairs.append({'question': question, 'answer': answer})
    return qa_pairs

# Retriever LLM - chooses the most relevant document
def retrieve_with_llm(query, docs):
    prompt = f"Given the query: '{query}', choose the most relevant document from the following:\n\n" + \
             "\n".join([f"{i+1}. {doc}" for i, doc in enumerate(docs)]) + \
             "\n\nReturn the number of the most relevant document."

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 10}
    }
    response = requests.post(RETRIEVER_API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        text = response.json()[0]["generated_text"]
        index = ''.join(filter(str.isdigit, text))
        return max(0, int(index.strip()) - 1) if index else 0
    else:
        return 0

# Generator LLM - returns final answer
def generate_llm_response(query, retrieved_answer):
    prompt = f"You are an intelligent MDCAT assistant. Use the following info to answer the user's question.\n\nQuestion: {query}\n\nRetrieved Info: {retrieved_answer}\n\nAnswer:"
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 256, "temperature": 0.7}
    }
    response = requests.post(GENERATOR_API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        text = response.json()[0]["generated_text"]
        return text.split("Answer:")[-1].strip()
    else:
        return f"Error: {response.status_code} - {response.text}"

# Dual LLM RAG Logic
def ask_mdcat_assistant_smart(query, sts_data, past_papers):
    all_qa = [("STS", {'question': q, 'answer': a}) for q, a in zip(sts_data['query'], sts_data['answer'])] + \
             [("Past Papers", qa) for qa in past_papers]

    questions = [qa['question'] for _, qa in all_qa]
    top_idx = retrieve_with_llm(query, questions)
    source, best_qa = all_qa[top_idx]
    response = generate_llm_response(query, best_qa['answer'])
    return response, source

# --- Streamlit UI ---
st.set_page_config(page_title="MDCAT Assistant", layout="centered")
st.title("🧠 MDCAT Assistant (Dual LLM RAG)")

with st.spinner("Loading data from GitHub..."):
    sts_data = load_sts_from_url(STS_CSV_URL)
    past_papers = load_past_paper_from_url(PAST_PAPERS_DOCX_URL)

query = st.text_input("Ask your MDCAT question:")

if query:
    with st.spinner("Retrieving and generating answer..."):
        response, source = ask_mdcat_assistant_smart(query, sts_data, past_papers)
        st.markdown(f"**Source:** {source}")
        st.markdown(f"**Assistant Response:**\n\n{response}")