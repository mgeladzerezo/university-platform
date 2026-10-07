import html
import re

_BLOCK_END = re.compile(r"</(p|h[1-6]|li|blockquote|pre)>|<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def html_to_text(body_html: str) -> str:
    with_breaks = _BLOCK_END.sub("\n", body_html)
    text = html.unescape(_TAG.sub("", with_breaks))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def chunk_text(text: str, max_chars: int = 600) -> list[str]:
    """Pack whole paragraphs into chunks of at most `max_chars`."""
    chunks: list[str] = []
    current = ""
    for paragraph in _split_long(text.splitlines(), max_chars):
        if current and len(current) + len(paragraph) + 1 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def _split_long(paragraphs: list[str], max_chars: int) -> list[str]:
    pieces = []
    for paragraph in paragraphs:
        while len(paragraph) > max_chars:
            cut = paragraph.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            pieces.append(paragraph[:cut])
            paragraph = paragraph[cut:].lstrip()
        if paragraph:
            pieces.append(paragraph)
    return pieces


def chunks_for_content(title: str, summary: str, body_html: str) -> list[str]:
    body = html_to_text(body_html)
    text = "\n".join(part for part in (summary, body) if part)
    # The title is repeated in every chunk so each one is understandable alone.
    return [f"{title}\n{chunk}" for chunk in chunk_text(text)] or [title]
