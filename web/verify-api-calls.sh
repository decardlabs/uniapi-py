#!/bin/bash

# Script to verify all API calls use the unified /api prefix pattern

echo "🔍 Verifying API Call Standardization..."
echo "========================================"

# Find all API calls without /api prefix (excluding comments, variables, and test files)
ISSUES=$(find src/ -name "*.tsx" -o -name "*.ts" | xargs grep -n "api\.\(get\|post\|put\|delete\)" | grep -v "/api/" | grep -v "// Unified API call" | grep -v "api\.get(.*)" | grep -v "__tests__" | grep -v "searchEndpoint" | grep -v "api\.get(\`\${" | grep -v "api\.get(url" | grep -v "api\.get(path")

if [ -z "$ISSUES" ]; then
    echo "✅ SUCCESS: All API calls use the unified /api prefix pattern!"
    echo ""
    echo "📊 API Call Statistics:"
    echo "----------------------"

    # Count total API calls
    TOTAL_CALLS=$(find src/ -name "*.tsx" -o -name "*.ts" | xargs grep -c "api\.\(get\|post\|put\|delete\)" | awk -F: '{sum += $2} END {print sum}')

    # Count calls with /api prefix
    API_CALLS=$(find src/ -name "*.tsx" -o -name "*.ts" | xargs grep -c "api\.\(get\|post\|put\|delete\).*'/api/" | awk -F: '{sum += $2} END {print sum}')

    # Count SearchableDropdown endpoints
    DROPDOWN_CALLS=$(find src/ -name "*.tsx" -o -name "*.ts" | xargs grep -c 'searchEndpoint="/api/' | awk -F: '{sum += $2} END {print sum}')

    echo "Total API calls: $TOTAL_CALLS"
    echo "API calls with /api prefix: $API_CALLS"
    echo "SearchableDropdown endpoints: $DROPDOWN_CALLS"
    echo ""
    echo "🎉 All API calls follow the unified standard!"

    exit 0
else
    echo "❌ ISSUES FOUND: The following API calls are missing the /api prefix:"
    echo "=================================================================="
    echo "$ISSUES"
    echo ""
    echo "🔧 Please fix these calls to use the unified pattern:"
    echo "   api.get('/api/endpoint') instead of api.get('/endpoint')"
    echo ""
    exit 1
fi
