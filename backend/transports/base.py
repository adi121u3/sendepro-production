from typing import Dict, Any, Optional

class DeliveryResult:
    def __init__(self, status: str, message: str, retryable: bool = False, message_id: Optional[str] = None):
        self.status = status
        self.message = message
        self.retryable = retryable
        self.message_id = message_id

    def to_dict(self):
        return {
            "status": self.status,
            "message": self.message,
            "retryable": self.retryable,
            "message_id": self.message_id,
        }

class BaseTransport:
    def __init__(self, account_config: Dict[str, Any]):
        self.account_config = account_config
        self.from_email = account_config.get("from_email") or account_config.get("username") or ""

    def success_result(self, status: str = "SUCCESS", message: str = "Success", message_id: Optional[str] = None) -> DeliveryResult:
        return DeliveryResult(status=status, message=message, retryable=False, message_id=message_id)

    def failure_result(self, status: str = "FAILED", message: str = "Failed", retryable: bool = False) -> DeliveryResult:
        return DeliveryResult(status=status, message=message, retryable=retryable)
