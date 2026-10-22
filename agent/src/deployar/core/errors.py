"""One error type: stable code for machines, Persian message for the UI, English detail for logs."""


class DeployarError(Exception):
    def __init__(self, code: str, message_fa: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.message_fa = message_fa
        self.detail = detail
