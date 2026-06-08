"""Object-storage abstraction and its implementations."""

from .base import StorageManager
from .gcs import GCSStorageManager
from .memory import InMemoryStorageManager

__all__ = ["StorageManager", "GCSStorageManager", "InMemoryStorageManager"]
