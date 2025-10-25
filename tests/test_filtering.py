"""
Test API-level filtering capabilities.
Demonstrates how to use status and tag filters.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.helpscout_client import HelpScoutClient


def test_filters():
    """Test various filter combinations."""
    print("=" * 70)
    print("TESTING API-LEVEL FILTERS")
    print("=" * 70)

    hs_client = HelpScoutClient()

    # Test 1: Get all conversations (baseline)
    print("\n1. Fetching ALL conversations...")
    all_convs = hs_client.get_all_conversations(status='all')
    print(f"   ✓ Found {len(all_convs)} total conversations")

    # Test 2: Active only (excludes spam, closed)
    print("\n2. Fetching ACTIVE conversations only...")
    active_convs = hs_client.get_all_conversations(status='active')
    print(f"   ✓ Found {len(active_convs)} active conversations")
    print(f"   Excluded: {len(all_convs) - len(active_convs)} conversations")

    # Test 3: Exclude specific tags
    print("\n3. Testing TAG EXCLUSION...")

    # First, let's see what tags exist in the conversations
    tags_found = set()
    for conv in all_convs[:50]:  # Sample first 50
        conv_tags = conv.get('tags', [])
        for tag in conv_tags:
            tags_found.add(tag)

    print(f"   Sample of available tags: {', '.join(sorted(tags_found)[:10])}")

    # Try excluding a tag if any exist
    if tags_found:
        test_tag = list(tags_found)[0]
        print(f"\n   Testing exclusion of tag: '{test_tag}'")
        filtered_convs = hs_client.get_all_conversations(
            exclude_tags=[test_tag]
        )
        print(f"   ✓ Found {len(filtered_convs)} conversations without '{test_tag}' tag")
        print(f"   Excluded: {len(all_convs) - len(filtered_convs)} conversations")
    else:
        print("   No tags found in sample conversations")

    # Test 4: Combine filters
    print("\n4. Testing COMBINED FILTERS...")
    if tags_found:
        combined_convs = hs_client.get_all_conversations(
            status='active',
            exclude_tags=[list(tags_found)[0]]
        )
        print(f"   ✓ Active conversations without '{list(tags_found)[0]}': {len(combined_convs)}")
    else:
        combined_convs = hs_client.get_all_conversations(status='active')
        print(f"   ✓ Active conversations: {len(combined_convs)}")

    # Summary
    print("\n" + "=" * 70)
    print("FILTER TEST SUMMARY")
    print("=" * 70)
    print(f"\nTotal conversations: {len(all_convs)}")
    print(f"Active conversations: {len(active_convs)}")
    print(f"Spam/Closed/Other: {len(all_convs) - len(active_convs)}")

    if tags_found:
        print(f"\nTags found in sample: {len(tags_found)}")
        print(f"Example tags: {', '.join(sorted(tags_found)[:5])}")

    print("\n" + "=" * 70)
    print("RECOMMENDED MIGRATION COMMAND")
    print("=" * 70)

    if tags_found:
        # Suggest excluding common test/internal tags
        common_exclude = []
        for tag in ['test', 'testing', 'low-priority', 'internal', 'spam']:
            if tag in tags_found:
                common_exclude.append(tag)

        if common_exclude:
            print(f"\npython migrate.py \\")
            print(f"  --status active \\")
            print(f"  --exclude-tags \"{','.join(common_exclude)}\"")
        else:
            print(f"\npython migrate.py --status active")
    else:
        print(f"\npython migrate.py --status active")

    print("\n")

    return True


if __name__ == "__main__":
    try:
        test_filters()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
