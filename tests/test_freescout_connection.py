"""
Test FreeScout API connection and authentication.
Run this first to validate FreeScout API access.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient, FreeScoutAPIError
from config.config import Config


def test_authentication():
    """Test FreeScout API authentication."""
    print("=" * 60)
    print("TEST: FreeScout API Authentication")
    print("=" * 60)

    try:
        client = FreeScoutClient()
        print(f"✓ Client initialized")
        print(f"  Base URL: {client.base_url}")
        print(f"  API Base: {client.api_base}")
        print(f"  API Key: {client.api_key[:10]}..." if len(client.api_key) > 10 else "  API Key: SET")

        # Try to fetch mailboxes as authentication test
        print("\nAttempting to fetch mailboxes...")
        mailboxes = client.get_mailboxes()

        print(f"✓ Authentication successful!")
        print(f"✓ Retrieved {len(mailboxes)} mailbox(es)")

        if mailboxes:
            print("\nMailboxes:")
            for mb in mailboxes:
                print(f"  - ID: {mb.get('id')}, Name: {mb.get('name')}")

        return True

    except FreeScoutAPIError as e:
        print(f"✗ API Error: {e}")
        if e.status_code:
            print(f"  Status Code: {e.status_code}")
        if e.response:
            print(f"  Response: {e.response}")
        return False

    except Exception as e:
        print(f"✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_users():
    """Test fetching users from FreeScout."""
    print("\n" + "=" * 60)
    print("TEST: Fetch FreeScout Users")
    print("=" * 60)

    try:
        client = FreeScoutClient()

        print("Fetching users...")
        response = client.get_users(page_size=10)

        users = response.get('_embedded', {}).get('users', [])
        print(f"✓ Retrieved {len(users)} user(s)")

        if users:
            print("\nUsers:")
            for user in users:
                print(f"  - ID: {user.get('id')}, "
                      f"Name: {user.get('firstName')} {user.get('lastName')}, "
                      f"Email: {user.get('email')}")

        return True

    except FreeScoutAPIError as e:
        print(f"✗ API Error: {e}")
        return False

    except Exception as e:
        print(f"✗ Unexpected Error: {e}")
        return False


def test_get_tags():
    """Test fetching tags from FreeScout."""
    print("\n" + "=" * 60)
    print("TEST: Fetch FreeScout Tags")
    print("=" * 60)

    try:
        client = FreeScoutClient()

        print("Fetching tags...")
        tags = client.get_tags()

        print(f"✓ Retrieved {len(tags)} tag(s)")

        if tags:
            print("\nTags:")
            for tag in tags[:20]:  # Show first 20
                print(f"  - {tag}")
            if len(tags) > 20:
                print(f"  ... and {len(tags) - 20} more")

        return True

    except FreeScoutAPIError as e:
        print(f"✗ API Error: {e}")
        return False

    except Exception as e:
        print(f"✗ Unexpected Error: {e}")
        return False


def main():
    """Run all connection tests."""
    print("\n" + "=" * 60)
    print("FREESCOUT API CONNECTION TESTS")
    print("=" * 60)
    print(f"FreeScout URL: {Config.FREESCOUT_URL}")
    print("=" * 60)

    results = []

    # Test 1: Authentication
    results.append(("Authentication", test_authentication()))

    # Test 2: Fetch Users
    results.append(("Fetch Users", test_get_users()))

    # Test 3: Fetch Tags
    results.append(("Fetch Tags", test_get_tags()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n✓ All tests passed! FreeScout API is ready.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Check configuration and FreeScout instance.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
