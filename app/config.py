"""
config.py — shared setup: Azure client, pricing, threshold.
Everything else imports from here instead of repeating this setup.
"""

import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

# ----- pricing (dollars per 1M tokens) -----
EMBED_PRICE_PER_1M = 0.02
CHAT_INPUT_PRICE_PER_1M = 0.25
CHAT_OUTPUT_PRICE_PER_1M = 2.00

# ----- the line that separates "found something real" from "found nothing" -----
SIMILARITY_THRESHOLD = 0.45

# ----- how many past exchanges to send to the model for context -----
HISTORY_LENGTH = 3


# Chroma's relevance scores are on a different scale than our hand-built
# cosine similarity, so they need their own threshold.
LC_SIMILARITY_THRESHOLD = 0.30