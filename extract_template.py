import zipfile
import xml.etree.ElementTree as ET
import sys
import os

docx_path = r"C:\Users\23546\AppData\Local\Claude-3p\local-agent-mode-sessions\7365f8a8-cbfc-493f-bc30-b66fc819b541\00000000-0000-4000-8000-000000000001\local_a434e900-c861-4691-86c1-ee9e60c11bc1\uploads\8ffdd22f-993f-4e34-a494-e4d8b5b91df2-1783266468485_2026嵌入式大赛应用赛道作品报告模板(1).docx"

try:
    with zipfile.ZipFile(docx_path) as z:
        xml_content = z.read('word/document.xml')

    tree = ET.fromstring(xml_content)

    # Also print structure info: tables, headings
    ns_uri = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

    for p in tree.iter(f'{{{ns_uri}}}p'):
        texts = []
        for t in p.iter(f'{{{ns_uri}}}t'):
            if t.text:
                texts.append(t.text)
        line = ''.join(texts)
        if line.strip():
            print(line)

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
