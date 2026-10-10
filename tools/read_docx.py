"""Extract the text of the utilities catalog .docx.

python-docx is not assumed; a .docx is a zip whose `word/document.xml` holds the text, so
this falls back to parsing that directly and restoring paragraph breaks from the XML rather
than returning one run-on line.

Usage:
    python tools/read_docx.py <path.docx>
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")

    # Paragraph and row boundaries become newlines; tabs become a space.
    xml = xml.replace("<w:tab/>", " ")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"</w:tr>", "\n", xml)
    xml = re.sub(r"</w:tc>", " | ", xml)
    # Drop the rest of the WordprocessingML vocabulary, keeping the text nodes.
    text = re.sub(r"<[^>]+>", "", xml)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                         ("&quot;", '"'), ("&apos;", "'"), ("&#8217;", "'")):
        text = text.replace(entity, char)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"  no such file: {path}")
        return 1
    body = extract(path)
    print(f"# {path.name}  ({len(body)} chars)\n")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())