def format_exception(exc: Exception) -> str:
    """Collapse an exception's message into a single clean line for safe
    printing/logging (raw SMTP/DB exceptions can contain newlines or byte
    strings that garble terminal output)."""
    message = str(exc).replace("\r", " ").replace("\n", " ")
    return " ".join(message.split())
