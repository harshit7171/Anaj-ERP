"""Application-specific exception hierarchy."""


class AnajError(Exception):
    """Base exception for expected application failures."""


class ValidationError(AnajError):
    """Raised when user or imported data fails validation."""


class DatabaseError(AnajError):
    """Raised when local persistence cannot complete safely."""


class CalculationError(AnajError):
    """Raised when a configured accounting calculation is invalid."""


class StateError(AnajError):
    """Raised when an operation is invalid for the current document state."""


class ClockTamperException(StateError):
    """Raised when the system date moves behind the protected last-use date."""


class LicenseWriteLockedError(StateError):
    """Raised when an expired or missing subscription attempts a data write."""


class CreditLimitBreachedError(ValidationError):
    """Raised when a transaction exceeds a farmer borrowing limit without override."""
