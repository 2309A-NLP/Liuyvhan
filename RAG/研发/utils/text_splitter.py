from __future__ import annotations


class TextSplitter:
    def __init__(self, chunk_size: int = 220, chunk_overlap: int = 40):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> list[str]:
        normalized = text.strip().replace("\r\n", "\n")
        if len(normalized) <= self.chunk_size:
            return [normalized]

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(start + self.chunk_size, len(normalized))
            chunks.append(normalized[start:end].strip())
            if end >= len(normalized):
                break
            start = max(0, end - self.chunk_overlap)
        return [chunk for chunk in chunks if chunk]
