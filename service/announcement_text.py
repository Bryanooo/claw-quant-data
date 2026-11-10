"""Resource-isolated, bounded PDF text extraction; no OCR or network access."""

import io, json, sys, resource


def main():
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    from pypdf import PdfReader

    data = sys.stdin.buffer.read(12 * 1024 * 1024 + 1)
    if len(data) > 12 * 1024 * 1024:
        raise ValueError("PDF byte budget exceeded")
    start, count = map(int, sys.argv[1:3])
    if start < 0 or not 1 <= count <= 25:
        raise ValueError("Invalid page budget")
    reader = PdfReader(io.BytesIO(data))
    if start >= len(reader.pages):
        raise ValueError("Requested page is beyond the document")
    parts = []
    stop = min(len(reader.pages), start + count)
    for i in range(start, stop):
        parts.append(reader.pages[i].extract_text() or "")
        if sum(map(len, parts)) > 200000:
            raise ValueError("Text budget exceeded")
    text = "\n\n".join(parts)
    print(
        json.dumps(
            {
                "text": text,
                "page_start": start,
                "page_stop": stop,
                "total_pages": len(reader.pages),
                "next_page": stop if stop < len(reader.pages) else None,
                "text_available": bool(text.strip()),
                "ocr_performed": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
