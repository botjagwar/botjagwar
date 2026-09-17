from random import randint
from time import sleep
from unittest import TestCase

from api.decorator import (
    run_once,
    singleton,
    threaded,
    critical_section,
    separate_process,
    reraise_exceptions,
    catch_exceptions,
    time_this,
    retry_on_fail,
)
from unittest import mock

s = ""


class DecoratorsTest(TestCase):
    def test_run_once(self):
        class M(object):
            @run_once
            def get_it(self):
                return randint(10000, 10000000)

        obj = M()
        result1 = obj.get_it()
        result2 = obj.get_it()
        self.assertEqual(result1, result2)

    def test_threaded(self):

        @threaded
        def function1():
            global s
            s += "x"
            sleep(0.4)

        def function2():
            global s
            s += "y"
            sleep(0.2)

        function2()
        function1()
        self.assertEqual(s, "yx")

    def test_singleton(self):
        @singleton
        class ThisIsMySingleton(object):
            def __init__(self):
                self.incrementing_counter = 1

            @property
            def increment(self):
                self.incrementing_counter += 1
                return self.incrementing_counter

        def test1():
            s = ThisIsMySingleton()
            return s.increment

        def test2():
            s = ThisIsMySingleton()
            return s.increment

        test1()
        test2()
        r = ThisIsMySingleton()
        self.assertEqual(r.incrementing_counter, 3)

    def test_critical_section(self) -> None:
        """Acquire and release the provided lock."""
        lock = mock.MagicMock()
        lock.__enter__.return_value = lock

        @critical_section(lock)
        def function() -> str:
            """Return a sample string."""
            return "value"

        result = function()
        self.assertEqual(result, "value")
        lock.__enter__.assert_called_once()
        lock.__exit__.assert_called_once_with(None, None, None)

    def test_critical_section_releases_lock_after_exception(self) -> None:
        """Release the provided lock when the wrapped function raises."""
        lock = mock.MagicMock()
        lock.__enter__.return_value = lock

        @critical_section(lock)
        def function() -> None:
            """Raise a sample error."""
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            function()

        lock.__exit__.assert_called_once()

    def test_run_once_equality(self) -> None:
        """Compare run_once decorators by wrapped function."""

        def func() -> str:
            """Return a sample string."""
            return "value"

        decorator_one = run_once(func)
        decorator_two = run_once(func)
        self.assertEqual(decorator_one, decorator_two)
        self.assertEqual(hash(decorator_one), hash(decorator_two))

    def test_singleton_creation_error(self) -> None:
        """Raise a singleton creation error when args are unexpected."""

        @singleton
        class BadSingleton(object):
            """Singleton requiring a constructor argument."""

            def __init__(self, value: int):
                self.value = value

        with self.assertRaises(Exception) as context:
            BadSingleton(1)

        self.assertEqual(context.exception.__class__.__name__, "SingletonCreationError")

    def test_separate_process(self) -> None:
        """Start a separate process."""
        with mock.patch("api.decorator.multiprocessing.Process") as process_class:
            process = process_class.return_value

            @separate_process
            def function() -> None:
                """No-op for process start."""
                return None

            function()
            process.start.assert_called_once()

    def test_reraise_exceptions(self) -> None:
        """Reraise exceptions as the requested type."""

        class OriginalError(Exception):
            """Original error type."""

        class WrappedError(Exception):
            """Wrapped error type."""

        @reraise_exceptions((OriginalError,), WrappedError)
        def function() -> None:
            """Raise the original error."""
            raise OriginalError("boom")

        with self.assertRaises(WrappedError):
            function()

    def test_catch_exceptions(self) -> None:
        """Return None when configured exceptions are raised."""

        class SampleError(Exception):
            """Sample error type."""

        @catch_exceptions(SampleError)
        def function() -> None:
            """Raise the sample error."""
            raise SampleError("boom")

        self.assertIsNone(function())

    def test_time_this_default(self) -> None:
        """Print timing output with the function name."""

        @time_this()
        def function() -> str:
            """Return a sample string."""
            return "value"

        with mock.patch("builtins.print") as mock_print:
            result = function()
        self.assertEqual(result, "value")
        self.assertIn("function", mock_print.call_args[0][0])

    def test_time_this_identifier(self) -> None:
        """Print timing output with a custom identifier."""

        @time_this(identifier="function")
        def function() -> str:
            """Return a sample string."""
            return "value"

        with mock.patch("builtins.print") as mock_print:
            result = function()
        self.assertEqual(result, "value")
        self.assertIn("function took", mock_print.call_args[0][0])

    def test_retry_on_fail_success_after_retries(self) -> None:
        """Retry until the function succeeds."""
        attempts = {"count": 0}

        @retry_on_fail((ValueError,), retries=2, time_between_retries=0)
        def function() -> str:
            """Fail twice before succeeding."""
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ValueError("fail")
            return "ok"

        result = function()
        self.assertEqual(result, "ok")

    def test_retry_on_fail_exhausted(self) -> None:
        """Raise after exceeding retries."""

        @retry_on_fail((ValueError,), retries=1, time_between_retries=0)
        def function() -> None:
            """Always fail."""
            raise ValueError("fail")

        with self.assertRaises(ValueError):
            function()
