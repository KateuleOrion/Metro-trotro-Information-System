class ApiError(Exception):
    """An error with an HTTP status and a message the user can read."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
