#!/bin/bash
# build_and_test.sh - Full rebuild and test for M65832 picolibc
#
# Rebuilds everything from scratch so all binaries match:
# 1. compiler-rt (soft int64, soft float)
# 2. picolibc (libc, libm)
# 3. Runs the full picolibc test suite
#
# Usage:
#   ./build_and_test.sh              Full rebuild + test
#   ./build_and_test.sh --skip-build Just run tests (use existing build)
#   ./build_and_test.sh --filter=mem Run only tests matching "mem"

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECTS_DIR="$(dirname "$SCRIPT_DIR")"

# Paths - all relative to project layout
LLVM_ROOT="$PROJECTS_DIR/llvm-m65832"
LLVM_BUILD="$LLVM_ROOT/build-fast"
PICOLIBC_SRC="$SCRIPT_DIR"
PICOLIBC_BUILD="$PROJECTS_DIR/picolibc-build-m65832"
COMPILER_RT_DIR="$LLVM_ROOT/m65832-stdlib/compiler-rt"
CROSS_FILE="$LLVM_ROOT/m65832-stdlib/picolibc/cross-m65832.txt"
TEST_RESULTS_DIR="$SCRIPT_DIR/test-results"

# Tools
CLANG="$LLVM_BUILD/bin/clang"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

# Parse arguments
SKIP_BUILD=false
TEST_ARGS=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        *)
            TEST_ARGS="$TEST_ARGS $1"
            shift
            ;;
    esac
done

echo -e "${BOLD}=========================================="
echo "M65832 Build and Test"
echo -e "==========================================${NC}"
echo ""
echo "Compiler:    $CLANG"
echo "Picolibc:    $PICOLIBC_SRC"
echo "Build dir:   $PICOLIBC_BUILD"
echo "Compiler-RT: $COMPILER_RT_DIR"
echo "Cross file:  $CROSS_FILE"
echo ""

# Verify tools exist
if [ ! -x "$CLANG" ]; then
    echo -e "${RED}ERROR: clang not found at $CLANG${NC}"
    echo "Build with: cd $LLVM_ROOT && ninja -C build-fast clang"
    exit 1
fi
if ! command -v meson &> /dev/null; then
    echo -e "${RED}ERROR: meson not found${NC}"
    exit 1
fi

if [ "$SKIP_BUILD" = false ]; then

    # =========================================================
    # Step 1: Rebuild compiler-rt
    # =========================================================
    echo -e "\n${BOLD}>>> Step 1/2: Rebuilding compiler-rt...${NC}"
    cd "$COMPILER_RT_DIR"
    make clean 2>/dev/null || true
    make -j8
    echo -e "${GREEN}    compiler-rt built: $COMPILER_RT_DIR/libcompiler_rt.a${NC}"

    # =========================================================
    # Step 2: Clean rebuild picolibc
    # =========================================================
    echo -e "\n${BOLD}>>> Step 2/2: Clean rebuilding picolibc...${NC}"
    rm -rf "$PICOLIBC_BUILD"

    meson setup "$PICOLIBC_BUILD" "$PICOLIBC_SRC" \
        --cross-file "$CROSS_FILE" \
        --buildtype=plain \
        -Ddebug=false \
        -Doptimization=1 \
        -Dmultilib=false \
        -Dtests=false \
        -Dprintf-aliases=false \
        -Dspecsdir=none \
        -Dfreestanding=true \
        -Dio-float-exact=false

    meson compile -C "$PICOLIBC_BUILD" -j8
    echo -e "${GREEN}    picolibc built: $PICOLIBC_BUILD${NC}"

    echo -e "\n${BOLD}Build complete.${NC}"
fi

# =========================================================
# Run tests
# =========================================================
echo -e "\n${BOLD}>>> Running picolibc test suite...${NC}"
cd "$SCRIPT_DIR"
mkdir -p "$TEST_RESULTS_DIR"

python3 run_picolibc_gtest.py --no-rebuild $TEST_ARGS

echo ""
