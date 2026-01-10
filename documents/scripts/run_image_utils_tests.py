import os
import sys
import importlib.util


def run_pytest(path):
    try:
        import pytest
    except Exception:
        return False
    return pytest.main([path])


def run_manual(path):
    # Execute the test module directly (it uses assertions)
    spec = importlib.util.spec_from_file_location('test_image_utils', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return True


if __name__ == '__main__':
    test_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'tests', 'test_image_utils.py'))
    print('Running image_utils tests')
    # try pytest if available
    ok = run_pytest(test_path)
    if ok is False:
        print('pytest not available — running manual runner')
        try:
            run_manual(test_path)
            print('Manual tests passed')
        except AssertionError as e:
            print('Manual tests failed:', e)
            sys.exit(2)
    else:
        # pytest returned exit code
        sys.exit(ok)
