"""
Validation script to verify migration from Help Scout to FreeScout.
Compares data between both systems to ensure integrity.
"""
import sys
import json
from pathlib import Path
from typing import Dict, List

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.helpscout_client import HelpScoutClient, HelpScoutAPIError
from api.freescout_client import FreeScoutClient, FreeScoutAPIError


class MigrationValidator:
    """Validates migrated data between Help Scout and FreeScout."""

    def __init__(self, progress_file: str = None):
        """
        Initialize validator.

        Args:
            progress_file: Optional path to migration progress file
        """
        self.hs_client = HelpScoutClient()
        self.fs_client = FreeScoutClient()

        # Load customer mapping from progress file
        self.customer_mapping = {}
        if progress_file:
            self._load_mapping(progress_file)

        # Validation results
        self.results = {
            'customers_validated': 0,
            'customers_failed': 0,
            'conversations_validated': 0,
            'conversations_failed': 0,
            'issues': []
        }

    def _load_mapping(self, progress_file: str):
        """Load customer mapping from progress file."""
        if not Path(progress_file).exists():
            print(f"⚠ Progress file not found: {progress_file}")
            return

        with open(progress_file, 'r') as f:
            data = json.load(f)
            self.customer_mapping = {int(k): int(v) for k, v in data.get('customer_mapping', {}).items()}

        print(f"✓ Loaded mapping for {len(self.customer_mapping)} customers")

    def validate_customer(self, hs_customer_id: int, fs_customer_id: int) -> bool:
        """
        Validate a single customer migration.

        Args:
            hs_customer_id: Help Scout customer ID
            fs_customer_id: FreeScout customer ID

        Returns:
            True if validation passed, False otherwise
        """
        try:
            # Fetch customer from both systems
            hs_customer = self.hs_client.get_customer(hs_customer_id)
            fs_customer = self.fs_client.get_customer(fs_customer_id)

            # Validate fields
            issues = []

            # Check first name
            if hs_customer.get('firstName') != fs_customer.get('firstName'):
                issues.append(f"First name mismatch: '{hs_customer.get('firstName')}' vs '{fs_customer.get('firstName')}'")

            # Check last name
            if hs_customer.get('lastName') != fs_customer.get('lastName'):
                issues.append(f"Last name mismatch: '{hs_customer.get('lastName')}' vs '{fs_customer.get('lastName')}'")

            # Check primary email
            hs_emails = hs_customer.get('emails', [])
            if hs_emails:
                hs_email = hs_emails[0] if isinstance(hs_emails[0], str) else hs_emails[0].get('value')
                fs_email = fs_customer.get('email')
                if hs_email and hs_email != fs_email:
                    issues.append(f"Email mismatch: '{hs_email}' vs '{fs_email}'")

            if issues:
                self.results['issues'].append({
                    'type': 'customer',
                    'hs_id': hs_customer_id,
                    'fs_id': fs_customer_id,
                    'issues': issues
                })
                self.results['customers_failed'] += 1
                return False
            else:
                self.results['customers_validated'] += 1
                return True

        except Exception as e:
            self.results['issues'].append({
                'type': 'customer',
                'hs_id': hs_customer_id,
                'fs_id': fs_customer_id,
                'error': str(e)
            })
            self.results['customers_failed'] += 1
            return False

    def validate_conversation(self, hs_conv_id: int, sample_check: bool = True) -> bool:
        """
        Validate a conversation exists and has correct thread count.

        Args:
            hs_conv_id: Help Scout conversation ID
            sample_check: If True, only validate basic fields (faster)

        Returns:
            True if validation passed, False otherwise
        """
        try:
            # Get Help Scout conversation
            hs_conv = self.hs_client.get_conversation(hs_conv_id)
            hs_threads = self.hs_client.get_conversation_threads(hs_conv_id)

            # We don't have direct conversation mapping, so we search by subject
            # This is a limitation - in production, we'd want to store conversation mapping
            subject = hs_conv.get('subject', '')

            # Get customer email to search conversations
            customer_ref = hs_conv.get('primaryCustomer', hs_conv.get('customer'))
            if not customer_ref:
                self.results['issues'].append({
                    'type': 'conversation',
                    'hs_id': hs_conv_id,
                    'error': 'No customer found in Help Scout conversation'
                })
                self.results['conversations_failed'] += 1
                return False

            customer_id = customer_ref.get('id')
            hs_customer = self.hs_client.get_customer(customer_id)

            # Get customer email
            emails = hs_customer.get('emails', [])
            if not emails:
                print(f"  ⚠ Skipping validation - no email for customer {customer_id}")
                return True

            customer_email = emails[0] if isinstance(emails[0], str) else emails[0].get('value')

            # Search for customer in FreeScout
            fs_customer = self.fs_client.search_customer_by_email(customer_email)
            if not fs_customer:
                self.results['issues'].append({
                    'type': 'conversation',
                    'hs_id': hs_conv_id,
                    'error': f'Customer not found in FreeScout: {customer_email}'
                })
                self.results['conversations_failed'] += 1
                return False

            # Search customer's conversations for matching subject
            fs_conversations = self.fs_client.get_conversations(customer_id=fs_customer['id'])
            matching_conv = None
            for conv in fs_conversations:
                if conv.get('subject') == subject:
                    matching_conv = conv
                    break

            if not matching_conv:
                self.results['issues'].append({
                    'type': 'conversation',
                    'hs_id': hs_conv_id,
                    'error': f'Conversation not found in FreeScout: "{subject}"'
                })
                self.results['conversations_failed'] += 1
                return False

            # Validate thread count (if sample check)
            if sample_check:
                fs_conv_full = self.fs_client.get_conversation(matching_conv['id'])
                fs_threads = fs_conv_full.get('_embedded', {}).get('threads', [])

                if len(fs_threads) != len(hs_threads):
                    self.results['issues'].append({
                        'type': 'conversation',
                        'hs_id': hs_conv_id,
                        'fs_id': matching_conv['id'],
                        'issues': [f"Thread count mismatch: {len(hs_threads)} vs {len(fs_threads)}"]
                    })
                    self.results['conversations_failed'] += 1
                    return False

            self.results['conversations_validated'] += 1
            return True

        except Exception as e:
            self.results['issues'].append({
                'type': 'conversation',
                'hs_id': hs_conv_id,
                'error': str(e)
            })
            self.results['conversations_failed'] += 1
            return False

    def validate_all_customers(self):
        """Validate all migrated customers from mapping."""
        print(f"\n{'=' * 70}")
        print("VALIDATING CUSTOMERS")
        print("=" * 70)

        if not self.customer_mapping:
            print("⚠ No customer mapping found")
            return

        print(f"\nValidating {len(self.customer_mapping)} customers...")

        for i, (hs_id, fs_id) in enumerate(self.customer_mapping.items(), 1):
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(self.customer_mapping)}")

            self.validate_customer(hs_id, fs_id)

        print(f"\n✓ Validation complete")
        print(f"  Passed: {self.results['customers_validated']}")
        print(f"  Failed: {self.results['customers_failed']}")

    def sample_validate_conversations(self, sample_size: int = 10):
        """
        Validate a sample of conversations.

        Args:
            sample_size: Number of conversations to validate
        """
        print(f"\n{'=' * 70}")
        print(f"SAMPLE VALIDATION: {sample_size} Conversations")
        print("=" * 70)

        # Get sample conversations from Help Scout
        print(f"\nFetching sample conversations from Help Scout...")
        hs_conversations = self.hs_client.get_conversations(status='all', page=1)
        sample_convs = hs_conversations.get('_embedded', {}).get('conversations', [])[:sample_size]

        print(f"✓ Validating {len(sample_convs)} conversations...")

        for i, conv in enumerate(sample_convs, 1):
            conv_id = conv.get('id')
            subject = conv.get('subject', '(No Subject)')
            print(f"\n  [{i}/{len(sample_convs)}] {subject} (ID: {conv_id})")
            self.validate_conversation(conv_id)

        print(f"\n✓ Validation complete")
        print(f"  Passed: {self.results['conversations_validated']}")
        print(f"  Failed: {self.results['conversations_failed']}")

    def print_summary(self):
        """Print validation summary."""
        print(f"\n{'=' * 70}")
        print("VALIDATION SUMMARY")
        print("=" * 70)

        print(f"\nCustomers:")
        print(f"  Validated: {self.results['customers_validated']}")
        print(f"  Failed: {self.results['customers_failed']}")

        print(f"\nConversations:")
        print(f"  Validated: {self.results['conversations_validated']}")
        print(f"  Failed: {self.results['conversations_failed']}")

        print(f"\nTotal Issues: {len(self.results['issues'])}")

        if self.results['issues']:
            print(f"\n{'=' * 70}")
            print("ISSUES FOUND")
            print("=" * 70)

            for issue in self.results['issues'][:10]:  # Show first 10
                print(f"\nType: {issue['type']}")
                if 'hs_id' in issue:
                    print(f"  Help Scout ID: {issue['hs_id']}")
                if 'fs_id' in issue:
                    print(f"  FreeScout ID: {issue['fs_id']}")
                if 'error' in issue:
                    print(f"  Error: {issue['error']}")
                if 'issues' in issue:
                    for i in issue['issues']:
                        print(f"  - {i}")

            if len(self.results['issues']) > 10:
                print(f"\n... and {len(self.results['issues']) - 10} more issues")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate Help Scout to FreeScout migration')
    parser.add_argument(
        '--progress-file',
        type=str,
        default='migration_progress.json',
        help='Path to migration progress file (default: migration_progress.json)'
    )
    parser.add_argument(
        '--customers',
        action='store_true',
        help='Validate all customers'
    )
    parser.add_argument(
        '--conversations',
        type=int,
        default=10,
        help='Number of conversations to sample validate (default: 10)'
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("MIGRATION VALIDATION")
    print("=" * 70)
    print("\nThis will validate data migrated from Help Scout to FreeScout.")
    print("=" * 70)

    # Initialize validator
    validator = MigrationValidator(progress_file=args.progress_file)

    # Validate customers
    if args.customers:
        validator.validate_all_customers()

    # Sample validate conversations
    if args.conversations > 0:
        validator.sample_validate_conversations(sample_size=args.conversations)

    # Print summary
    validator.print_summary()

    # Return status
    if validator.results['customers_failed'] > 0 or validator.results['conversations_failed'] > 0:
        print("\n⚠ Validation found issues")
        return 1
    else:
        print("\n✓ Validation passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
