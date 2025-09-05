import json
import sys
from scrape_ai_mode import scrape_ai_mode

if __name__ == '__main__':
    # Get query from command line or use default
    query = sys.argv[1] if len(sys.argv) > 1 else "tell me about reprompt ai"
    
    print(f"Running query: {query}")
    
    # Run the search with intelligent polling
    try:
        structured_result = scrape_ai_mode(query, max_wait_seconds=10)
    except TimeoutError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
    
    # Save to JSON file
    with open("final_search_extraction.json", "w", encoding="utf-8") as f:
        json.dump(structured_result, f, indent=2, ensure_ascii=False)
    
    # Print results
    print(f"\nResults extracted:")
    print(f"- {len(structured_result['text_blocks'])} text blocks")
    print(f"- {len(structured_result['references'])} references") 
    print(f"- {len(structured_result['inline_images'])} inline images")
    
    print(f"\nJSON saved to: final_search_extraction.json")
    print(f"\nFirst few text blocks:")
    for i, block in enumerate(structured_result['text_blocks'][:3]):
        if block['type'] == 'paragraph':
            snippet = block['snippet'][:100] + "..." if len(block['snippet']) > 100 else block['snippet']
            print(f"  {i+1}. [paragraph] {snippet}")
        elif block['type'] == 'list':
            print(f"  {i+1}. [list] {len(block['items'])} items")