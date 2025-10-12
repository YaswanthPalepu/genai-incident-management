# test_kb.py - FIXED VERSION
import sys
sys.path.insert(0, 'backend')

from db.chromadb import parse_knowledge_base, load_and_vectorize_kb, hybrid_search_kb, clear_knowledge_base

def main():
    # Optional: Clear and start fresh
    print("Clearing existing knowledge base...")
    clear_knowledge_base()
    
    # Step 1: Parse KB
    print("Step 1: Parsing KB...")
    chunks = parse_knowledge_base()
    print(f"Found {len(chunks)} chunks")
    for chunk in chunks:
        print(f"  - KB_ID: {chunk['kb_id']}, Content length: {len(chunk['content'])}")
        # Print first 100 chars of content to verify parsing
        print(f"    Preview: {chunk['content'][:100]}...")

    # Step 2: Load and vectorize
    print("\nStep 2: Loading and vectorizing KB...")
    try:
        load_and_vectorize_kb()
        print("KB vectorized successfully")
    except Exception as e:
        print(f"Failed to vectorize KB: {e}")
        return

    # Step 3: Test search
    print("\nStep 3: Testing search...")
    test_queries = [
        "outlook not opening",
        "wifi drops",
        "computer slow", 
        "printer not working",
        "email",
        "connection"
    ]

    for query in test_queries:
        results = hybrid_search_kb(query, n_results=2)
        print(f"\nQuery: '{query}'")
        if results:
            for i, result in enumerate(results):
                print(f"  Result {i+1}:")
                print(f"    KB_ID: {result['kb_id']}")
                print(f"    Similarity: {result['similarity']:.3f}")
                print(f"    Preview: {result['content'][:80]}...")
        else:
            print("  No results found")

if __name__ == "__main__":
    main()