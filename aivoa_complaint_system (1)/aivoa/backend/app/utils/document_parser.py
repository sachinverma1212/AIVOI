"""
Extracts raw text from an uploaded complaint document.

Per the assignment, production-grade OCR/parsing is NOT required — this
handles the common cases (plain text, .eml, .docx, .pdf with a text layer)
so the demo can run end to end on realistic sample files.
"""
import email
import io

import pdfplumber
import docx

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".eml"}


def extract_text(filename: str, content: bytes) -> str:
    lower = filename.lower()

    if lower.endswith(".txt"):
        return content.decode("utf-8", errors="ignore")

    if lower.endswith(".eml"):
        msg = email.message_from_bytes(content)
        parts = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    parts.append(part.get_payload(decode=True).decode("utf-8", errors="ignore"))
        else:
            parts.append(msg.get_payload(decode=True).decode("utf-8", errors="ignore"))
        header = f"From: {msg.get('From', '')}\nSubject: {msg.get('Subject', '')}\n\n"
        return header + "\n".join(parts)

    if lower.endswith(".docx"):
        document = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in document.paragraphs)

    if lower.endswith(".pdf"):
        text_chunks = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_chunks.append(page_text)
        return "\n".join(text_chunks)

    # Fallback: try decoding as plain text
    return content.decode("utf-8", errors="ignore")
