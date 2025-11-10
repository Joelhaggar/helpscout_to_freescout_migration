"""
Validate that all customers in batch files have proper emails.

This script checks:
1. All customers have at least one email
2. Emails are properly formatted
3. No @migration.local placeholder emails exist
4. Email count per customer
"""
import json
from pathlib import Path
import re

class CustomerEmailValidator:
    """Validate customer emails in batch files."""

    def __init__(self, export_dir: str = None):
        self.project_root = Path(__file__).parent
        self.export_dir = Path(export_dir) if export_dir else self.project_root / 'helpscout_export'
        self.customers_dir = self.export_dir / 'customers'

    def validate_email(self, email: str) -> bool:
        """Check if email is valid format."""
        if not email or '@migration.local' in email:
            return False
        # Basic email validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def validate_batch_file(self, batch_file: Path) -> dict:
        """Validate all customers in a batch file."""
        results = {
            'file': batch_file.name,
            'total_customers': 0,
            'with_email': 0,
            'without_email': 0,
            'invalid_emails': 0,
            'valid_emails': 0,
            'issues': []
        }

        try:
            with open(batch_file, 'r') as f:
                customers = json.load(f)

            results['total_customers'] = len(customers)

            for customer in customers:
                customer_id = customer.get('id')
                first_name = customer.get('firstName', '')
                last_name = customer.get('lastName', '')

                # Extract email from _embedded.emails
                emails = customer.get('_embedded', {}).get('emails', [])

                if not emails:
                    results['without_email'] += 1
                    results['issues'].append({
                        'customer_id': customer_id,
                        'name': f"{first_name} {last_name}".strip(),
                        'issue': 'NO_EMAIL'
                    })
                    continue

                # Get first email
                first_email_obj = emails[0]
                if isinstance(first_email_obj, dict):
                    email = first_email_obj.get('value', '')
                else:
                    email = first_email_obj

                if not email:
                    results['without_email'] += 1
                    results['issues'].append({
                        'customer_id': customer_id,
                        'name': f"{first_name} {last_name}".strip(),
                        'issue': 'EMPTY_EMAIL'
                    })
                    continue

                results['with_email'] += 1

                if self.validate_email(email):
                    results['valid_emails'] += 1
                else:
                    results['invalid_emails'] += 1
                    results['issues'].append({
                        'customer_id': customer_id,
                        'name': f"{first_name} {last_name}".strip(),
                        'email': email,
                        'issue': 'INVALID_FORMAT' if not re.match(r'^[a-zA-Z0-9._%+-]+@', email) else 'PLACEHOLDER_EMAIL'
                    })

        except Exception as e:
            results['issues'].append({
                'issue': 'FILE_READ_ERROR',
                'error': str(e)
            })

        return results

    def run(self):
        """Run validation on all batch files."""
        print("="*80)
        print("CUSTOMER EMAIL VALIDATION")
        print("="*80)

        if not self.customers_dir.exists():
            print("✗ Customers directory not found")
            return

        batch_files = sorted(self.customers_dir.glob('customers_batch_*.json'))
        print(f"\nValidating {len(batch_files)} customer batch files...\n")

        total_results = {
            'total_customers': 0,
            'with_email': 0,
            'without_email': 0,
            'invalid_emails': 0,
            'valid_emails': 0,
            'all_issues': []
        }

        for batch_file in batch_files:
            results = self.validate_batch_file(batch_file)

            # Accumulate totals
            total_results['total_customers'] += results['total_customers']
            total_results['with_email'] += results['with_email']
            total_results['without_email'] += results['without_email']
            total_results['invalid_emails'] += results['invalid_emails']
            total_results['valid_emails'] += results['valid_emails']
            total_results['all_issues'].extend(results['issues'])

            # Print batch summary
            status = "✓" if results['invalid_emails'] == 0 and results['without_email'] == 0 else "✗"
            print(f"{status} {results['file']:<30s} | "
                  f"Total: {results['total_customers']:4d} | "
                  f"Valid: {results['valid_emails']:4d} | "
                  f"Invalid: {results['invalid_emails']:4d} | "
                  f"Missing: {results['without_email']:4d}")

        # Print summary
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        print(f"Total customers:     {total_results['total_customers']:,}")
        print(f"With email:          {total_results['with_email']:,}")
        print(f"Without email:       {total_results['without_email']:,}")
        print(f"Valid emails:        {total_results['valid_emails']:,}")
        print(f"Invalid emails:      {total_results['invalid_emails']:,}")

        # Validation result
        if total_results['without_email'] == 0 and total_results['invalid_emails'] == 0:
            print("\n✅ ALL CUSTOMERS HAVE VALID EMAILS - SAFE TO IMPORT")
        else:
            print("\n⚠️  VALIDATION ISSUES FOUND - REVIEW BEFORE IMPORTING")

            if total_results['all_issues']:
                print(f"\nFirst 20 issues:")
                for issue in total_results['all_issues'][:20]:
                    if 'customer_id' in issue:
                        print(f"  - Customer {issue['customer_id']}: {issue['name']:30s} | {issue.get('issue', 'UNKNOWN')}")
                        if 'email' in issue:
                            print(f"    Email: {issue['email']}")
                    else:
                        print(f"  - {issue}")

        print("\n" + "="*80)


if __name__ == '__main__':
    validator = CustomerEmailValidator()
    validator.run()
