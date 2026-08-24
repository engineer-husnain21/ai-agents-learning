"""
rewriting_lc.py — same rewrite prompt as app/rewriting.py (task 5.5),
using LangChain's AzureChatOpenAI instead of a raw openai client call.
"""

import os
from dotenv import load_dotenv
load_dotenv()
from langchain_openai import AzureChatOpenAI

chat_model = AzureChatOpenAI(
    model="gpt-5-mini",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)


def rewrite_question_lc(question, history):
    if not history:
        return question, 0, 0

    history_lines = []
    for turn in history:
        history_lines.append(f"Q: {turn['question']}\nA: {turn['answer']}")
    history_text = "\n\n".join(history_lines)

    prompt = f"""You rewrite a follow-up question into a standalone question, using the conversation history below.

Rules:
- ONLY resolve references (she, that, it, the same one, etc.) using the history.
- Never answer the question.
- Never add information that isn't already in the conversation.
- If the question is already standalone (no unresolved references), return it EXACTLY unchanged.

Conversation history:
{history_text}

Follow-up question: {question}

Standalone question:"""

    response = chat_model.invoke(prompt)

    rewritten = response.content.strip()
    input_tokens = response.usage_metadata["input_tokens"]
    output_tokens = response.usage_metadata["output_tokens"]

    return rewritten, input_tokens, output_tokens