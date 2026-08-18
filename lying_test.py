"""
lying_test.py — ONE-TIME test script with the grounding rules REMOVED.
This is intentional (task requirement) to see what the model does
without the "answer only from context" rule. Not meant to be used normally.
"""

import json
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

# Load a few random chunks (not necessarily relevant to the question)
with open("chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

random_chunks = chunks[10:13]   # just pick some arbitrary chunks
context = "\n\n".join(f"[Chunk {c['chunk_id']}]: {c['text']}" for c in random_chunks)

question = "who was pakistan's first international cricket team captain" 

# NOTICE: no grounding rules here, unlike answer.py
prompt = f"""Context:
{context}

Question: {question}

Answer:"""

response = client.chat.completions.create(
    model="gpt-5-mini",
    messages=[{"role": "user", "content": prompt}]
)

print("Prompt sent (rules removed on purpose):")
print(prompt)
print()
print("Model's answer:")
print(response.choices[0].message.content)