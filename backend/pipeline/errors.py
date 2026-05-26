class PipelineError(Exception):
    def __init__(self, step_name: str, message: str, original_exc: Exception | None = None):
        self.step_name = step_name
        self.message = message
        self.original_exc = original_exc
        super().__init__(f"[{step_name}] {message}")
