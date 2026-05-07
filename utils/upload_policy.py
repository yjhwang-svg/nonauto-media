def should_upload(errors: list[str], allow_partial: bool = False) -> bool:
    return not errors or allow_partial
