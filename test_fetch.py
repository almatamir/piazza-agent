import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from scraper.piazza_client import get_network, fetch_posts
from scraper.parser import parse_posts

print("=== Piazza Connection Test ===\n")

try:
    print("1. Connecting to Piazza...")
    network = get_network()
    print("   Connected!\n")

    print("2. Fetching posts...")
    raw = fetch_posts(network, since_id=None)
    print(f"   Got {len(raw)} posts\n")

    print("3. Parsing posts...")
    posts = parse_posts(raw)
    print(f"   Parsed {len(posts)} posts\n")

    print("4. Sample (last 3 posts):")
    for p in posts[:3]:
        print(f"\n   [{p['created']}] #{p['nr']} — {p['subject']}")
        print(f"   Tags: {p['tags']}")
        has_answer = "YES" if p["instructor_answer"] else "no"
        print(f"   Instructor answer: {has_answer}")

except Exception as e:
    print(f"\nERROR: {e}")
    sys.exit(1)

print("\n=== Test passed! ===")
