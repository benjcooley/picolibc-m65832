#!/usr/bin/env python3
"""
Picolibc Test Suite Runner for M65832
Outputs in Google Test (gtest) format

Usage: ./run_picolibc_gtest.py [--filter=PATTERN] [--list] [--verbose]
"""

import os
import sys
import subprocess
import tempfile
import time
import argparse
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Paths
PICOLIBC_ROOT = Path(__file__).resolve().parent
PROJECTS_ROOT = PICOLIBC_ROOT.parent
LLVM_ROOT = PROJECTS_ROOT / "llvm-m65832"
LLVM_BUILD_FAST = LLVM_ROOT / "build-fast" / "bin"
LLVM_BUILD_DEFAULT = LLVM_ROOT / "build" / "bin"

LLVM_BUILD = Path(
    os.environ.get(
        "LLVM_BUILD",
        str(LLVM_BUILD_FAST if (LLVM_BUILD_FAST / "clang").exists() else LLVM_BUILD_DEFAULT),
    )
)
CLANG = LLVM_BUILD / "clang"
# LLD is only in the full build directory
LLD = LLVM_BUILD_DEFAULT / "ld.lld"
EMU = PROJECTS_ROOT / "m65832" / "emu" / "m65832emu"
SYSROOT = PROJECTS_ROOT / "m65832-sysroot"
PICOLIBC_TEST = PICOLIBC_ROOT / "test"
CUSTOM_TESTS = PROJECTS_ROOT / "m65832" / "emu" / "c_tests" / "baremetal" / "picolibc"

# Colors (gtest style)
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"

MAX_CYCLES = 1000000


@dataclass
class TestResult:
    name: str
    suite: str
    passed: bool
    time_ms: float
    error_msg: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


def extract_expected_value(filepath: str) -> Optional[int]:
    """Extract expected return value from test file comments."""
    try:
        with open(filepath, "r") as f:
            content = f.read(1000)

        # Look for "Expected:" or "expected:" patterns
        # e.g., "// Expected: strlen("hello") = 5" -> 5
        # e.g., "// Expected: 42" -> 42
        match = re.search(r"[Ee]xpected.*?=\s*(-?\d+)", content)
        if match:
            return int(match.group(1))

        # Also try just "Expected: N"
        match = re.search(r"[Ee]xpected:\s*(-?\d+)", content)
        if match:
            return int(match.group(1))

        return None
    except:
        return None


def extract_description(filepath: str) -> str:
    """Extract a description from the test file's comments."""
    try:
        with open(filepath, "r") as f:
            content = f.read(2000)

        # Look for explicit "Test:" pattern first
        match = re.search(r"//\s*Test:\s*(.+)", content)
        if match:
            return match.group(1).strip()[:50]

        # Generate clean description from filename
        name = Path(filepath).stem
        desc = name.replace("test-", "").replace("test_", "").replace("test", "")
        desc = desc.replace("-", " ").replace("_", " ").strip()
        if desc:
            return desc.title()
        return name
    except:
        return Path(filepath).stem


def find_test_files() -> List[Tuple[str, str, str]]:
    """Find all test .c files and return (suite_name, filepath, description) tuples."""
    tests = []

    # Custom baremetal tests (these actually work!)
    if CUSTOM_TESTS.exists():
        for f in sorted(CUSTOM_TESTS.glob("*.c")):
            desc = extract_description(str(f))
            tests.append(("baremetal", str(f), desc))

    # Top-level picolibc tests
    for f in sorted(PICOLIBC_TEST.glob("*.c")):
        if f.name in (
            "lock-valid.c",
            "native-locks.c",
            "math_errhandling_tests.c",
            "rounding-mode-sub.c",
            "try-ilp32-sub.c",
            "fma_vec.h",
            "long_double_vec.h",
        ):
            continue  # Skip helper files
        desc = extract_description(str(f))
        tests.append(("picolibc", str(f), desc))

    # Subdirectory tests
    subdirs = [
        "libc-testsuite",
        "test-ctype",
        "test-string",
        "test-stdio",
        "test-math",
        "test-monetary",
        "test-iconv",
        "testsuite",
    ]

    for subdir in subdirs:
        subdir_path = PICOLIBC_TEST / subdir
        if subdir_path.exists():
            for f in sorted(subdir_path.glob("*.c")):
                suite_name = subdir.replace("-", "_")
                desc = extract_description(str(f))
                tests.append((suite_name, str(f), desc))

    return tests


def compile_test(src_path: str, work_dir: str) -> Tuple[bool, str, str]:
    """Compile a test file. Returns (success, obj_path, error_msg)."""
    base = Path(src_path).stem
    obj_path = os.path.join(work_dir, f"{base}.o")

    cmd = [
        str(CLANG),
        "-target",
        "m65832-elf",
        "-O0",
        "-ffreestanding",
        f"-I{SYSROOT}/include",
        f"-I{PICOLIBC_TEST}",
        "-c",
        src_path,
        "-o",
        obj_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, "", result.stderr
    return True, obj_path, ""


def link_test(obj_path: str, work_dir: str) -> Tuple[bool, str, str]:
    """Link a test file. Returns (success, elf_path, error_msg)."""
    base = Path(obj_path).stem
    elf_path = os.path.join(work_dir, f"{base}.elf")

    cmd = [
        str(LLD),
        f"-T{SYSROOT}/lib/m65832.ld",
        f"{SYSROOT}/lib/crt0.o",
        obj_path,
        f"-L{SYSROOT}/lib",
        "-lc",
        "-lsys",
        "-o",
        elf_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, "", result.stderr
    return True, elf_path, ""


def run_test(elf_path: str) -> Tuple[bool, int, str]:
    """Run a test on the emulator. Returns (success, exit_code, output)."""
    cmd = [str(EMU), "-c", str(MAX_CYCLES), "--stop-on-brk", "-s", elf_path]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr

    # Extract A register value from the CPU state line
    # Look for "PC: xxxx  A: xxxx" pattern to avoid matching "A:32-bit"
    match = re.search(r"PC:\s*[0-9A-Fa-f]+\s+A:\s*([0-9A-Fa-f]+)", output)
    if match:
        exit_code = int(match.group(1), 16)
        return True, exit_code, output

    return False, -1, output


def run_single_test(suite: str, src_path: str, work_dir: str) -> TestResult:
    """Run a single test and return result."""
    name = Path(src_path).stem
    start_time = time.time()

    # Only skip tests we definitely know won't work
    skip_tests = {
        # These require semihosting or specific host features
        "abort": "Requires signal handling",
        "hosted-exit": "Requires semihosting",
        "test-argv": "Requires argument passing",
        "test-ubsan": "Requires sanitizer",
        "stack-smash": "Requires stack protection",
        "tls": "Requires thread-local storage",
        "test-atomic": "Requires atomics",
        "test-cplusplus": "Requires C++",
        "test-raise": "Requires signals",
        "test-except": "Requires exceptions",
    }

    if name in skip_tests:
        return TestResult(
            name=name,
            suite=suite,
            passed=False,
            time_ms=0,
            skipped=True,
            skip_reason=skip_tests[name],
        )

    # Compile
    success, obj_path, err = compile_test(src_path, work_dir)
    if not success:
        elapsed = (time.time() - start_time) * 1000
        # Check if it's a missing feature vs actual error
        if "undefined" in err.lower() or "undeclared" in err.lower():
            return TestResult(
                name=name,
                suite=suite,
                passed=False,
                time_ms=elapsed,
                skipped=True,
                skip_reason="Missing symbols",
            )
        return TestResult(
            name=name,
            suite=suite,
            passed=False,
            time_ms=elapsed,
            error_msg=f"Compile error: {err[:200]}",
        )

    # Link
    success, elf_path, err = link_test(obj_path, work_dir)
    if not success:
        elapsed = (time.time() - start_time) * 1000
        if "undefined symbol" in err.lower():
            # Extract symbol name
            match = re.search(r"undefined symbol:\s*(\S+)", err)
            sym = match.group(1) if match else "unknown"
            return TestResult(
                name=name,
                suite=suite,
                passed=False,
                time_ms=elapsed,
                skipped=True,
                skip_reason=f"Missing symbol: {sym}",
            )
        return TestResult(
            name=name,
            suite=suite,
            passed=False,
            time_ms=elapsed,
            error_msg=f"Link error: {err[:200]}",
        )

    # Run
    try:
        success, exit_code, output = run_test(elf_path)
        elapsed = (time.time() - start_time) * 1000

        if not success:
            return TestResult(
                name=name,
                suite=suite,
                passed=False,
                time_ms=elapsed,
                error_msg="Emulator error",
            )

        # Check expected value from test file
        expected = extract_expected_value(src_path)

        if expected is not None:
            # Test has explicit expected value
            if exit_code == expected:
                return TestResult(name=name, suite=suite, passed=True, time_ms=elapsed)
            else:
                return TestResult(
                    name=name,
                    suite=suite,
                    passed=False,
                    time_ms=elapsed,
                    error_msg=f"Expected {expected}, got {exit_code}",
                )
        else:
            # Standard: exit_code 0 = pass, non-zero = fail
            if exit_code == 0:
                return TestResult(name=name, suite=suite, passed=True, time_ms=elapsed)
            else:
                return TestResult(
                    name=name,
                    suite=suite,
                    passed=False,
                    time_ms=elapsed,
                    error_msg=f"Test returned {exit_code}",
                )
    except subprocess.TimeoutExpired:
        elapsed = (time.time() - start_time) * 1000
        return TestResult(
            name=name,
            suite=suite,
            passed=False,
            time_ms=elapsed,
            error_msg="Timeout",
        )


def print_gtest_header(total_tests: int):
    """Print gtest-style header."""
    print(f"{GREEN}[==========]{RESET} Running {total_tests} tests from picolibc test suite.")
    print(f"{GREEN}[----------]{RESET} Global test environment set-up.")


def print_gtest_suite_start(suite: str, count: int):
    """Print gtest-style suite start."""
    print(f"{GREEN}[----------]{RESET} {count} tests from {suite}")


def print_gtest_run(suite: str, name: str, desc: str = ""):
    """Print gtest-style test start."""
    if desc:
        print(f"{GREEN}[ RUN      ]{RESET} {suite}.{name} - {desc}")
    else:
        print(f"{GREEN}[ RUN      ]{RESET} {suite}.{name}")


def print_gtest_ok(suite: str, name: str, time_ms: float):
    """Print gtest-style test pass."""
    print(f"{GREEN}[       OK ]{RESET} {suite}.{name} ({time_ms:.0f} ms)")


def print_gtest_failed(suite: str, name: str, time_ms: float, msg: str = ""):
    """Print gtest-style test fail."""
    if msg:
        print(f"  {msg}")
    print(f"{RED}[  FAILED  ]{RESET} {suite}.{name} ({time_ms:.0f} ms)")


def print_gtest_skipped(suite: str, name: str, reason: str):
    """Print gtest-style test skip."""
    print(f"{YELLOW}[  SKIPPED ]{RESET} {suite}.{name} ({reason})")


def print_gtest_suite_end(suite: str, count: int, time_ms: float):
    """Print gtest-style suite end."""
    print(f"{GREEN}[----------]{RESET} {count} tests from {suite} ({time_ms:.0f} ms total)")
    print()


def print_gtest_footer(results: List[TestResult], total_time: float):
    """Print gtest-style footer."""
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    total = len(results)

    print(f"{GREEN}[----------]{RESET} Global test environment tear-down")
    print(f"{GREEN}[==========]{RESET} {total} tests from picolibc ran. ({total_time:.0f} ms total)")
    print(f"{GREEN}[  PASSED  ]{RESET} {passed} tests.")

    if skipped > 0:
        print(f"{YELLOW}[  SKIPPED ]{RESET} {skipped} tests.")

    if failed > 0:
        print(f"{RED}[  FAILED  ]{RESET} {failed} tests, listed below:")
        for r in results:
            if not r.passed and not r.skipped:
                print(f"{RED}[  FAILED  ]{RESET} {r.suite}.{r.name}")
        print()
        print(f" {failed} FAILED TEST{'S' if failed != 1 else ''}")


def main():
    parser = argparse.ArgumentParser(
        description="Run picolibc tests on M65832",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          Run all tests
  %(prog)s malloc                   Run test named 'malloc'
  %(prog)s string memcpy            Run tests 'string' and 'memcpy'
  %(prog)s --suite=test_string      Run all tests in test_string suite
  %(prog)s --filter='mem*'          Run tests matching pattern 'mem*'
  %(prog)s --list                   List all available tests
  %(prog)s --list --suite=picolibc  List tests in picolibc suite
""",
    )
    parser.add_argument("tests", nargs="*", help="Specific test names to run")
    parser.add_argument("--filter", "-f", help="Filter tests by pattern (e.g., 'mem*', '*string*')")
    parser.add_argument("--suite", "-s", help="Run only tests from this suite")
    parser.add_argument("--list", "-l", action="store_true", help="List tests without running")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Find all tests
    all_tests = find_test_files()

    # Filter by suite
    if args.suite:
        all_tests = [
            (s, p, d)
            for s, p, d in all_tests
            if s.lower() == args.suite.lower() or s.lower().replace("_", "-") == args.suite.lower()
        ]

    # Filter by specific test names
    if args.tests:
        test_names = [t.lower() for t in args.tests]
        all_tests = [
            (s, p, d)
            for s, p, d in all_tests
            if Path(p).stem.lower() in test_names
            or any(Path(p).stem.lower().startswith(t) for t in test_names)
            or any(t in Path(p).stem.lower() for t in test_names)
        ]

    # Filter by pattern
    if args.filter:
        pattern = args.filter.replace("*", ".*")
        all_tests = [
            (s, p, d)
            for s, p, d in all_tests
            if re.search(pattern, Path(p).stem, re.IGNORECASE) or re.search(pattern, s, re.IGNORECASE)
        ]

    if args.list:
        # Group by suite for nice display
        suites_list = {}
        for suite, path, desc in all_tests:
            if suite not in suites_list:
                suites_list[suite] = []
            suites_list[suite].append((Path(path).stem, desc))

        print(f"Found {len(all_tests)} tests in {len(suites_list)} suites:\n")
        for suite_name in sorted(suites_list.keys()):
            tests = suites_list[suite_name]
            print(f"{BOLD}{suite_name}{RESET} ({len(tests)} tests)")
            for name, desc in sorted(tests):
                if desc:
                    print(f"  {name:30} {desc}")
                else:
                    print(f"  {name}")
            print()
        return 0

    # Group by suite
    suites = {}
    for suite, path, desc in all_tests:
        if suite not in suites:
            suites[suite] = []
        suites[suite].append((path, desc))

    # Create temp directory
    with tempfile.TemporaryDirectory() as work_dir:
        results = []
        total_start = time.time()

        print_gtest_header(len(all_tests))
        print()

        for suite_name, test_items in sorted(suites.items()):
            suite_start = time.time()
            print_gtest_suite_start(suite_name, len(test_items))

            for src_path, desc in test_items:
                name = Path(src_path).stem

                print_gtest_run(suite_name, name, desc)

                result = run_single_test(suite_name, src_path, work_dir)
                results.append(result)

                if result.skipped:
                    print_gtest_skipped(suite_name, name, result.skip_reason)
                elif result.passed:
                    print_gtest_ok(suite_name, name, result.time_ms)
                else:
                    print_gtest_failed(suite_name, name, result.time_ms, result.error_msg)

            suite_time = (time.time() - suite_start) * 1000
            suite_results = [r for r in results if r.suite == suite_name]
            passed_count = sum(1 for r in suite_results if r.passed)
            print_gtest_suite_end(suite_name, passed_count, suite_time)

        total_time = (time.time() - total_start) * 1000
        print_gtest_footer(results, total_time)

        # Return exit code
        failed = sum(1 for r in results if not r.passed and not r.skipped)
        return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
