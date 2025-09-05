"""
Pause execution for a specified number of seconds.
Lets the agent wait while a server restarts, etc.
"""
from time import sleep
import pydantic as py


class WaitArgs(py.BaseModel):
    seconds: int = py.Field(description="Seconds to sleep (1‑600)", ge=1, le=600)


class WaitTool:
    NAME = "sleep_seconds"
    DESC = "Pause the conversation for N seconds (max 600)."

    def function_spec(self):
        schema = WaitArgs.model_json_schema()
        schema["additionalProperties"] = False
        return {"name": self.NAME, "description": self.DESC, "parameters": schema}

    def __call__(self, *args):
        arguments = args[-1]
        parsed = WaitArgs(**arguments)
        sleep(parsed.seconds)
        return f"Slept {parsed.seconds} s."
