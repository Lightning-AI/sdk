"""Tests for logging metaclass functionality."""

from abc import ABC, abstractmethod
from unittest import mock

import pytest

from lightning_sdk.utils.logging import TrackCallsABCMeta, TrackCallsMeta


class TestTrackCallsMeta:
    """Tests for TrackCallsMeta."""

    def test_simple_class_instantiation(self):
        """Test that a simple class with TrackCallsMeta can be instantiated."""

        class SimpleClass(metaclass=TrackCallsMeta):
            def __init__(self, value: int):
                self.value = value

            def get_value(self) -> int:
                return self.value

        obj = SimpleClass(42)
        assert obj.value == 42
        assert obj.get_value() == 42

    def test_class_with_properties(self):
        """Test that classes with properties work correctly."""

        class ClassWithProperties(metaclass=TrackCallsMeta):
            def __init__(self, value: int):
                self._value = value

            @property
            def value(self) -> int:
                return self._value

            @value.setter
            def value(self, new_value: int) -> None:
                self._value = new_value

        obj = ClassWithProperties(10)
        assert obj.value == 10
        obj.value = 20
        assert obj.value == 20

    def test_class_with_class_methods(self):
        """Test that class methods work correctly."""

        class ClassWithClassMethod(metaclass=TrackCallsMeta):
            _counter = 0

            @classmethod
            def increment(cls) -> int:
                cls._counter += 1
                return cls._counter

        assert ClassWithClassMethod.increment() == 1
        assert ClassWithClassMethod.increment() == 2

    def test_class_with_static_methods(self):
        """Test that static methods work correctly."""

        class ClassWithStaticMethod(metaclass=TrackCallsMeta):
            @staticmethod
            def add(a: int, b: int) -> int:
                return a + b

        assert ClassWithStaticMethod.add(5, 3) == 8

    def test_method_exceptions_are_propagated(self):
        """Test that exceptions raised in methods are properly propagated."""

        class ClassWithException(metaclass=TrackCallsMeta):
            def raise_error(self):
                raise ValueError("Test error")

        obj = ClassWithException()
        with pytest.raises(ValueError, match="Test error"):
            obj.raise_error()

    def test_dunder_methods_excluded(self):
        """Test that dunder methods (except __init__ and __call__) are not wrapped."""

        class ClassWithDunderMethods(metaclass=TrackCallsMeta):
            def __init__(self, value: int):
                self.value = value

            def __str__(self) -> str:
                return f"Value: {self.value}"

            def __repr__(self) -> str:
                return f"ClassWithDunderMethods({self.value})"

            def __eq__(self, other) -> bool:
                return self.value == other.value if isinstance(other, ClassWithDunderMethods) else False

        obj1 = ClassWithDunderMethods(42)
        obj2 = ClassWithDunderMethods(42)
        obj3 = ClassWithDunderMethods(100)

        assert str(obj1) == "Value: 42"
        assert repr(obj1) == "ClassWithDunderMethods(42)"
        assert obj1 == obj2
        assert obj1 != obj3


class TestTrackCallsABCMeta:
    """Tests for TrackCallsABCMeta."""

    def test_abstract_class_with_metaclass(self):
        """Test that abstract classes work with TrackCallsABCMeta."""

        class AbstractBase(ABC, metaclass=TrackCallsABCMeta):
            @abstractmethod
            def get_value(self) -> int:
                pass

        class ConcreteClass(AbstractBase):
            def __init__(self, value: int):
                self.value = value

            def get_value(self) -> int:
                return self.value

        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            AbstractBase()

        # Can instantiate concrete class
        obj = ConcreteClass(42)
        assert obj.get_value() == 42

    def test_abstract_class_inheritance(self):
        """Test that abstract class inheritance works correctly."""

        class BaseClass(ABC, metaclass=TrackCallsABCMeta):
            @abstractmethod
            def process(self, value: int) -> int:
                pass

            def double(self, value: int) -> int:
                return value * 2

        class DerivedClass(BaseClass):
            def process(self, value: int) -> int:
                return value + 10

        obj = DerivedClass()
        assert obj.process(5) == 15
        assert obj.double(5) == 10

    def test_multiple_inheritance_levels(self):
        """Test that multiple inheritance levels work correctly."""

        class Level1(ABC, metaclass=TrackCallsABCMeta):
            @abstractmethod
            def method1(self) -> str:
                pass

        class Level2(Level1):
            def method1(self) -> str:
                return "level2"

            def method2(self) -> str:
                return "method2"

        class Level3(Level2):
            def method3(self) -> str:
                return "method3"

        obj = Level3()
        assert obj.method1() == "level2"
        assert obj.method2() == "method2"
        assert obj.method3() == "method3"

    def test_abstract_properties(self):
        """Test that abstract properties work correctly."""

        class AbstractWithProperty(ABC, metaclass=TrackCallsABCMeta):
            @property
            @abstractmethod
            def name(self) -> str:
                pass

        class ConcreteWithProperty(AbstractWithProperty):
            def __init__(self, name: str):
                self._name = name

            @property
            def name(self) -> str:
                return self._name

        obj = ConcreteWithProperty("test")
        assert obj.name == "test"


class TestMetaclassIntegration:
    """Integration tests to ensure metaclass doesn't break real SDK classes."""

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_job_base_class_compatibility(self, mock_client):
        """Test that _BaseJob works with the metaclass."""
        from lightning_sdk.job.base import _BaseJob

        # Verify the metaclass is applied
        assert isinstance(_BaseJob, type)
        assert hasattr(_BaseJob, "__abstractmethods__")

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_owner_base_class_compatibility(self, mock_client):
        """Test that Owner works with the metaclass."""
        from lightning_sdk.owner import Owner

        # Verify the metaclass is applied
        assert isinstance(Owner, type)
        assert hasattr(Owner, "__abstractmethods__")

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_plugin_base_class_compatibility(self, mock_client):
        """Test that _Plugin works with the metaclass."""
        from lightning_sdk.plugin import _Plugin

        # Verify the metaclass is applied
        assert isinstance(_Plugin, type)
        assert hasattr(_Plugin, "__abstractmethods__")

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_studio_class_compatibility(self, mock_client):
        """Test that Studio works with the metaclass."""
        from lightning_sdk.studio import Studio

        # Verify the metaclass is applied
        assert isinstance(Studio, type)

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_teamspace_class_compatibility(self, mock_client):
        """Test that Teamspace works with the metaclass."""
        from lightning_sdk.teamspace import Teamspace

        # Verify the metaclass is applied
        assert isinstance(Teamspace, type)

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_agent_class_compatibility(self, mock_client):
        """Test that Agent works with the metaclass."""
        from lightning_sdk.agents import Agent

        # Verify the metaclass is applied
        assert isinstance(Agent, type)

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_ai_hub_class_compatibility(self, mock_client):
        """Test that AIHub works with the metaclass."""
        from lightning_sdk.ai_hub import AIHub

        # Verify the metaclass is applied
        assert isinstance(AIHub, type)

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_deployment_class_compatibility(self, mock_client):
        """Test that Deployment works with the metaclass."""
        from lightning_sdk.deployment import Deployment

        # Verify the metaclass is applied
        assert isinstance(Deployment, type)


class TestMetaclassLogging:
    """Tests for the actual logging behavior."""

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_successful_method_call_logging(self, mock_client):
        """Test that successful method calls are logged."""

        class TestClass(metaclass=TrackCallsMeta):
            def test_method(self, value: int) -> int:
                return value * 2

        obj = TestClass()
        result = obj.test_method(5)
        assert result == 10

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_failed_method_call_logging(self, mock_client):
        """Test that failed method calls are logged with error info."""

        class TestClass(metaclass=TrackCallsMeta):
            def test_method(self) -> None:
                raise RuntimeError("Test error")

        obj = TestClass()
        with pytest.raises(RuntimeError, match="Test error"):
            obj.test_method()

    @mock.patch("lightning_sdk.utils.logging.LightningClient")
    def test_property_access_logging(self, mock_client):
        """Test that property access is logged."""

        class TestClass(metaclass=TrackCallsMeta):
            def __init__(self):
                self._value = 42

            @property
            def value(self) -> int:
                return self._value

        obj = TestClass()
        result = obj.value
        assert result == 42
