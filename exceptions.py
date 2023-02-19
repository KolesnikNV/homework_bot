class SendMessageException(Exception):
    """Кастомная ошибка для отправки сообщения."""

    pass


class ErrorException(Exception):
    """Кастомная ошибка."""

    pass


class EndpointException(ErrorException):
    """Кастомная ошибка."""

    pass


class CheckResponseException(ErrorException):
    """Кастомная ошибка."""

    pass


class ParseStatusException(ErrorException):
    """Кастомная ошибка."""

    pass


class NoTokensException(Exception):
    """Кастомная ошибка."""

    pass
