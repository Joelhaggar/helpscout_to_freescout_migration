"""
Test FreeScout customer creation and retrieval.
Tests the customer API endpoints.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.freescout_client import FreeScoutClient, FreeScoutAPIError
import time


def test_create_customer():
    """Test creating a customer in FreeScout."""
    print("=" * 60)
    print("TEST: Create Customer in FreeScout")
    print("=" * 60)

    try:
        client = FreeScoutClient()

        # Create test customer data
        timestamp = int(time.time())
        customer_data = {
            "firstName": "Test",
            "lastName": "Customer",
            "email": f"test.customer.{timestamp}@example.com",
            "phone": "+1-555-0100",
            "jobTitle": "QA Tester",
            "organization": "Test Organization"
        }

        print("\nCreating customer with data:")
        for key, value in customer_data.items():
            print(f"  {key}: {value}")

        print("\nSending request to FreeScout...")
        created_customer = client.create_customer(customer_data)

        print(f"\n✓ Customer created successfully!")
        print(f"  Customer ID: {created_customer.get('id')}")
        print(f"  Name: {created_customer.get('firstName')} {created_customer.get('lastName')}")
        print(f"  Email: {created_customer.get('email')}")

        # Return ID for cleanup
        return created_customer.get('id')

    except FreeScoutAPIError as e:
        print(f"\n✗ API Error: {e}")
        if e.status_code:
            print(f"  Status Code: {e.status_code}")
        if e.response:
            print(f"  Response: {e.response}")
        return None

    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_get_customer(customer_id):
    """Test retrieving a customer by ID."""
    print("\n" + "=" * 60)
    print("TEST: Retrieve Customer by ID")
    print("=" * 60)

    if not customer_id:
        print("✗ No customer ID provided (previous test failed)")
        return False

    try:
        client = FreeScoutClient()

        print(f"\nFetching customer ID: {customer_id}")
        customer = client.get_customer(customer_id)

        print(f"\n✓ Customer retrieved successfully!")
        print(f"  ID: {customer.get('id')}")
        print(f"  Name: {customer.get('firstName')} {customer.get('lastName')}")
        print(f"  Email: {customer.get('email')}")
        print(f"  Phone: {customer.get('phone')}")
        print(f"  Organization: {customer.get('organization')}")

        # Show all emails if multiple
        emails = customer.get('emails', [])
        if len(emails) > 1:
            print(f"  All Emails: {', '.join(emails)}")

        return True

    except FreeScoutAPIError as e:
        print(f"\n✗ API Error: {e}")
        return False

    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        return False


def test_search_customer_by_email(email):
    """Test searching for a customer by email."""
    print("\n" + "=" * 60)
    print("TEST: Search Customer by Email")
    print("=" * 60)

    if not email:
        print("✗ No email provided")
        return False

    try:
        client = FreeScoutClient()

        print(f"\nSearching for customer with email: {email}")
        customer = client.search_customer_by_email(email)

        if customer:
            print(f"\n✓ Customer found!")
            print(f"  ID: {customer.get('id')}")
            print(f"  Name: {customer.get('firstName')} {customer.get('lastName')}")
            print(f"  Email: {customer.get('email')}")
            return True
        else:
            print(f"\n✗ No customer found with email: {email}")
            return False

    except FreeScoutAPIError as e:
        print(f"\n✗ API Error: {e}")
        return False

    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        return False


def test_update_customer(customer_id):
    """Test updating a customer."""
    print("\n" + "=" * 60)
    print("TEST: Update Customer")
    print("=" * 60)

    if not customer_id:
        print("✗ No customer ID provided")
        return False

    try:
        client = FreeScoutClient()

        update_data = {
            "jobTitle": "Senior QA Tester (Updated)",
            "background": "This is a test customer created during migration testing."
        }

        print(f"\nUpdating customer ID: {customer_id}")
        print("Update data:")
        for key, value in update_data.items():
            print(f"  {key}: {value}")

        updated_customer = client.update_customer(customer_id, update_data)

        print(f"\n✓ Customer updated successfully!")
        print(f"  Job Title: {updated_customer.get('jobTitle')}")

        return True

    except FreeScoutAPIError as e:
        print(f"\n✗ API Error: {e}")
        return False

    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        return False


def main():
    """Run all customer tests."""
    print("\n" + "=" * 60)
    print("FREESCOUT CUSTOMER API TESTS")
    print("=" * 60)

    results = []
    customer_id = None
    customer_email = None

    # Test 1: Create Customer
    print("\n[1/4] Creating customer...")
    customer_id = test_create_customer()
    results.append(("Create Customer", customer_id is not None))

    if customer_id:
        # Get email for search test
        try:
            client = FreeScoutClient()
            customer = client.get_customer(customer_id)
            customer_email = customer.get('email')
        except:
            pass

    # Test 2: Get Customer
    print("\n[2/4] Retrieving customer...")
    result = test_get_customer(customer_id)
    results.append(("Get Customer", result))

    # Test 3: Search by Email
    print("\n[3/4] Searching by email...")
    result = test_search_customer_by_email(customer_email)
    results.append(("Search by Email", result))

    # Test 4: Update Customer
    print("\n[4/4] Updating customer...")
    result = test_update_customer(customer_id)
    results.append(("Update Customer", result))

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

    if customer_id:
        print(f"\nℹ Test customer ID: {customer_id}")
        print("  (You may want to delete this test customer manually)")

    if passed == total:
        print("\n✓ All customer tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
