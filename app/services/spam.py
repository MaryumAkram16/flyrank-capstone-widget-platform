def is_spam(honeypot_value: str) -> bool:
    """The widget renders a `website` field hidden via CSS (display:none) that
    real visitors never see or fill. Bots that fill every input on the page
    fill it too — a non-empty value is a reliable bot signal."""
    return bool(honeypot_value and honeypot_value.strip() != "")
