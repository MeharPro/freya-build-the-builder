"""Include the original plain-assert tests in standard unittest discovery."""
import unittest
import test_lint


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in vars(test_lint).items()
                              if name.startswith('test_') and callable(fn))
