class HomeworkAPIError(Exception):
    """Общее исключение для ошибок при запросах к API домашних заданий."""
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class HomeworkNotFoundError(HomeworkAPIError):
    """Исключение для ошибок, когда домашка не найдена."""
    def __init__(self, message="Домашка не найдена"):
        super().__init__(message)


class HomeworkAPIResponseError(HomeworkAPIError):
    """Исключение для ошибок, связанных с неверным ответом от API."""
    def __init__(self, message="Неверный ответ от API"):
        super().__init__(message)
