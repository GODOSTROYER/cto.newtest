#!/bin/bash
# System Validation Script for Trading Execution Loop

echo "================================================"
echo "Trading Execution Loop - System Validation"
echo "================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counter
CHECKS_PASSED=0
TOTAL_CHECKS=0

check_file() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $2"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $2 - MISSING: $1"
    fi
}

check_dir() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $2"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $2 - MISSING: $1"
    fi
}

echo "1. Core Files"
echo "-------------"
check_file "main.py" "Main entry point"
check_file "requirements.txt" "Python dependencies"
check_file "Dockerfile" "Docker configuration"
check_file "docker-compose.yml" "Docker Compose configuration"
check_file ".env.example" "Environment example"
check_file "pytest.ini" "Pytest configuration"
check_file "README.md" "Documentation"
check_file "IMPLEMENTATION.md" "Implementation docs"
echo ""

echo "2. Source Code Structure"
echo "------------------------"
check_dir "src" "Source directory"
check_dir "src/config" "Configuration module"
check_dir "src/storage" "Storage module"
check_dir "src/execution" "Execution module"
check_dir "src/cli" "CLI module"
echo ""

echo "3. Execution Components"
echo "----------------------"
check_file "src/execution/signal_router.py" "Signal Router"
check_file "src/execution/governor.py" "Governor"
check_file "src/execution/filters.py" "Market Filters"
check_file "src/execution/order_manager.py" "Order Manager"
check_file "src/execution/execution_loop.py" "Execution Loop"
echo ""

echo "4. Storage Components"
echo "--------------------"
check_file "src/storage/models.py" "Data Models"
check_file "src/storage/sqlite_manager.py" "SQLite Manager"
echo ""

echo "5. Configuration & CLI"
echo "---------------------"
check_file "src/config/settings.py" "Settings"
check_file "src/cli/dashboard.py" "Dashboard"
echo ""

echo "6. Tests"
echo "--------"
check_dir "tests" "Tests directory"
check_file "tests/test_basic_functionality.py" "Basic functionality tests"
echo ""

echo "================================================"
echo "Validation Summary"
echo "================================================"
echo -e "Checks passed: ${GREEN}${CHECKS_PASSED}${NC}/${TOTAL_CHECKS}"

if [ $CHECKS_PASSED -eq $TOTAL_CHECKS ]; then
    echo -e "${GREEN}✓ All validation checks passed!${NC}"
    echo ""
    echo "System is ready for:"
    echo "  • docker-compose up --build"
    echo "  • pytest tests/test_basic_functionality.py"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some validation checks failed${NC}"
    echo ""
    exit 1
fi
