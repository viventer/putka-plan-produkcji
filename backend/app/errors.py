class DomainError(Exception):
    """Base class for errors mapped to an HTTP response."""


class NotFoundError(DomainError):
    """The store or a product does not exist."""


class BusinessRuleError(DomainError):
    """A business rule rejected the order."""
