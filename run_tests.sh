#!/bin/bash
#
# Test runner for FreeScout API tests
# Run this script to execute all FreeScout tests in sequence
#

echo "======================================"
echo "FREESCOUT API TEST SUITE"
echo "======================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠ Virtual environment not found."
    echo "  Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "  Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo "Running tests..."
echo ""

# Run connection test
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TEST 1: Connection & Authentication"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python tests/test_freescout_connection.py
CONNECTION_RESULT=$?

if [ $CONNECTION_RESULT -ne 0 ]; then
    echo ""
    echo "✗ Connection test failed. Please check your FreeScout configuration."
    echo "  Make sure FreeScout is running and the .env file is configured correctly."
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TEST 2: Customer API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python tests/test_freescout_customer.py
CUSTOMER_RESULT=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TEST 3: Conversation API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python tests/test_freescout_conversation.py
CONVERSATION_RESULT=$?

# Summary
echo ""
echo "======================================"
echo "OVERALL TEST SUMMARY"
echo "======================================"

TOTAL_TESTS=3
PASSED_TESTS=0

if [ $CONNECTION_RESULT -eq 0 ]; then
    echo "✓ Connection & Authentication: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "✗ Connection & Authentication: FAILED"
fi

if [ $CUSTOMER_RESULT -eq 0 ]; then
    echo "✓ Customer API: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "✗ Customer API: FAILED"
fi

if [ $CONVERSATION_RESULT -eq 0 ]; then
    echo "✓ Conversation API: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "✗ Conversation API: FAILED"
fi

echo "======================================"
echo "Results: $PASSED_TESTS/$TOTAL_TESTS tests passed"
echo "======================================"

if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo ""
    echo "✓ All tests passed! FreeScout API is ready for migration."
    exit 0
else
    echo ""
    echo "✗ Some tests failed. Please review the output above."
    exit 1
fi
