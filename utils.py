def find_all(string, substring):
    import re
    escaped_substring = re.escape(substring)
    return [m.start() for m in re.finditer(escaped_substring, string)]