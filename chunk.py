"""
chunk.py — text chunker
Usage: python chunk.py mybook.txt --size 1000 --overlap 200
"""

import argparse   # standard library: reads --size, --overlap from command line
import json        # standard library: to save chunks.json


def chunk_text(text, size, overlap):
    """
    Splits `text` into overlapping chunks.
    size    = how many characters per chunk
    overlap = how many characters repeat from the end of the previous chunk
    """
    # safety net: agar overlap >= size ho to infinite loop ban jayega, isliye
    # ye check kaam shuru hone se pehle hi ho jana chahiye, har iteration mein nahi
    if size - overlap <= 0:
        raise ValueError("overlap must be smaller than size")

    chunks = []
    start = 0
    chunk_id = 0

    while start < len(text):
        end = start + size                  # where this chunk stops
        piece = text[start:end]              # slice the text

        chunks.append({
            "chunk_id": chunk_id,
            "text": piece,
            "start_position": start
        })

        chunk_id += 1
        start += (size - overlap)            # move forward, but "step back" by overlap

    return chunks


def main():
    # 1. Command-line arguments define karo
    parser = argparse.ArgumentParser(description="Split a text file into overlapping chunks.")
    parser.add_argument("filename", help="path to a .txt file")
    parser.add_argument("--size", type=int, required=True, help="characters per chunk")
    parser.add_argument("--overlap", type=int, required=True, help="overlapping characters between chunks")
    args = parser.parse_args()

    # 2. File read karo
    with open(args.filename, "r", encoding="utf-8") as f:
        text = f.read()

    # 3. Chunk karo
    chunks = chunk_text(text, args.size, args.overlap)

    # 4. Summary print karo
    print(f"Total characters: {len(text)}")
    print(f"Number of chunks: {len(chunks)}")
    print()
    print("--- Chunk 1 ---")
    print(chunks[0]["text"])
    print()
    if len(chunks) > 1:
        print("--- Chunk 2 ---")
        print(chunks[1]["text"])

    # 5. JSON mein save karo
    with open("chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print("\nSaved all chunks to chunks.json")


if __name__ == "__main__":
    main()