"""
search.py — simple word-matching search over chunks
Usage: python search.py chunks.json "who is the main character"
"""

import argparse   # standard library: reads chunks_file and question from command line
import json        # standard library: to load chunks.json
import string       # standard library: gives us a list of punctuation characters


# STOP WORDS: common words that appear almost everywhere and tell us nothing
# about which chunk is special. We ignore these when scoring.
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "and", "or", "but", "with",
    "as", "by", "it", "this", "that", "these", "those", "i", "you",
    "he", "she", "we", "they", "do", "does", "did", "what", "who",
    "where", "when", "why", "how", "not", "no", "so", "if", "then",
    "than", "his", "her", "its", "their", "my", "your", "our"
}


def clean_and_split(text):
    """
    Takes a piece of text, lowercases it, removes punctuation,
    splits it into words, and removes stop words.
    "Weather," and "weather" become the same word after this.
    """
    text = text.lower()
    # remove punctuation: replace each punctuation character with nothing
    for punct in string.punctuation:
        text = text.replace(punct, "")
    words = text.split()   # splits on whitespace
    words = [w for w in words if w not in STOP_WORDS]   # drop stop words
    return set(words)       # set = no duplicates, and fast to compare


def score_chunk(question_words, chunk_words):
    """
    Score = how many words the chunk shares with the question.
    Using set intersection: words that appear in BOTH sets.
    """
    common_words = question_words & chunk_words   # & = set intersection
    return len(common_words)


def main():
    # 1. Command-line arguments define karo
    parser = argparse.ArgumentParser(description="Search chunks.json for the chunks most related to a question.")
    parser.add_argument("chunks_file", help="path to chunks.json (from chunk.py)")
    parser.add_argument("question", help="the question to search for, in quotes")
    args = parser.parse_args()

    # 2. chunks.json load karo
    with open(args.chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # 3. Question ko clean karke words nikaalo
    question_words = clean_and_split(args.question)

    # 4. Har chunk ko score do
    scored_chunks = []
    for chunk in chunks:
        chunk_words = clean_and_split(chunk["text"])
        score = score_chunk(question_words, chunk_words)
        scored_chunks.append({
            "chunk_id": chunk["chunk_id"],
            "score": score,
            "text": chunk["text"]
        })

    # 5. Score ke hisaab se sort karo (sabse zyada score pehle)
    scored_chunks.sort(key=lambda c: c["score"], reverse=True)

    # 6. Top 3 print karo
    print(f"Question: {args.question}")
    print()
    top_3 = scored_chunks[:3]
    for rank, chunk in enumerate(top_3, start=1):
        print(f"--- Rank {rank} | chunk_id: {chunk['chunk_id']} | score: {chunk['score']} ---")
        print(chunk["text"][:200])   # first 200 characters only
        print()


if __name__ == "__main__":
    main()