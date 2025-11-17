#!/bin/bash
# Quick test script: Run bulk import with only 10 conversations (actual import, not dry-run)
# This allows you to test the real import pipeline before running the full bulk import

set -e

cd "$(dirname "$0")"

echo "Activating virtual environment..."
source ../venv/bin/activate

echo ""
echo "========================================================================"
echo "BULK IMPORT - TEST RUN (10 conversations)"
echo "========================================================================"
echo ""
echo "This will import the 10 newest conversations to FreeScout."
echo "Progress updates will appear every 10 conversations."
echo ""

python bulk_import_conversations.py --max-conversations 10

echo ""
echo "========================================================================"
echo "Test run complete!"
echo "State has been saved to bulk_import_state.json"
echo ""
echo "Next steps:"
echo "  - Review the results above"
echo "  - To resume full import: python bulk_import_conversations.py --resume"
echo "  - To run full import from scratch: python bulk_import_conversations.py"
echo "========================================================================"
