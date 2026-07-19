"""Runner for ACL pressure tests — run all or by name."""
import asyncio, sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tests.acls.test_acl01_pressure import (
    test_acl_p01_repeated_pause_resume,
    test_acl_p02_concurrent_pause_resume,
    test_acl_p03_heavy_handler_pause,
    test_acl_p04_extended_pause,
    test_acl_p05_multi_pause_single_round,
    test_acl_p06_isolated_runtime_instances,
    reset_counters,
    PASS, FAIL,
)

TESTS = [
    ("ACL-P01", test_acl_p01_repeated_pause_resume),
    ("ACL-P02", test_acl_p02_concurrent_pause_resume),
    ("ACL-P03", test_acl_p03_heavy_handler_pause),
    ("ACL-P04", test_acl_p04_extended_pause),
    ("ACL-P05", test_acl_p05_multi_pause_single_round),
    ("ACL-P06", test_acl_p06_isolated_runtime_instances),
]

async def run_all(skip_p04: bool = False):
    passed = failed = 0
    for name, fn in TESTS:
        if skip_p04 and "P04" in name:
            print(f"\n--- SKIP {name} (60s extended pause) ---")
            continue
        reset_counters()
        try:
            ok = await fn()
            if ok:
                passed += 1
                print(f"\n  [PASS] {name}")
            else:
                failed += 1
                print(f"\n  [FAIL] {name}")
        except Exception as e:
            failed += 1
            traceback.print_exc()
            print(f"  [ERROR] {name}: {e}")
        print("-" * 60)

    print(f"\nACL PRESSURE: {passed}/{passed+failed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    skip_p04 = "--skip-p04" in sys.argv
    result = asyncio.run(run_all(skip_p04=skip_p04))
    sys.exit(0 if result else 1)
