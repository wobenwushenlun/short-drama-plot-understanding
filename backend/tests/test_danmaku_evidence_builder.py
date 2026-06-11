import json
import zipfile
from pathlib import Path

from backend.scripts.build_danmaku_evidence import build_danmaku_evidence


def _write_minimal_xlsx(path: Path, rows: list[list[object]]) -> None:
    shared_strings: list[str] = []
    shared_index: dict[str, int] = {}

    def cell_ref(col_index: int, row_index: int) -> str:
        return f"{chr(ord('A') + col_index)}{row_index}"

    def cell_xml(value: object, col_index: int, row_index: int) -> str:
        ref = cell_ref(col_index, row_index)
        if isinstance(value, (int, float)):
            return f'<c r="{ref}"><v>{value}</v></c>'
        text = str(value)
        if text not in shared_index:
            shared_index[text] = len(shared_strings)
            shared_strings.append(text)
        return f'<c r="{ref}" t="s"><v>{shared_index[text]}</v></c>'

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(cell_xml(value, col_index, row_index) for col_index, value in enumerate(row))
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')

    shared_items = "".join(f"<si><t>{text}</t></si>" for text in shared_strings)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""")
        zf.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        zf.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>""")
        zf.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""")
        zf.writestr("xl/sharedStrings.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">{shared_items}</sst>""")
        zf.writestr("xl/worksheets/sheet1.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>""")


def test_build_danmaku_evidence_exports_only_aggregated_hotspots(tmp_path):
    source = tmp_path / "danmaku.xlsx"
    output = tmp_path / "hotspots.json"
    rows = [
        ["剧名称", "group_title", "发弹幕时刻相对于视频起始时间偏移量", "累计点赞数", "弹幕内容"],
        ["家里家外", "第1集", 12.0, 3, "这段太心疼了"],
        ["家里家外", "第1集", 13.5, 12, "家里人真的太气人"],
        ["家里家外", "第1集", 14.0, 20, "反转要来了"],
        ["家里家外", "第1集", 20.0, 18, "打脸太爽了"],
        ["家里家外", "第1集", 21.0, 9, "终于反转"],
        ["家里家外", "第2集", 55.0, 4, "站女主"],
        ["无关剧", "第1集", 10.0, 100, "不应进入结果"],
    ]
    _write_minimal_xlsx(source, rows)

    payload = build_danmaku_evidence(source, output)

    assert output.exists()
    assert payload["privacy"]["rawContentExported"] is False
    assert payload["privacy"]["rawRowsExported"] is False
    assert "jiali_jiawai_ep01" in payload["episodes"]
    episode = payload["episodes"]["jiali_jiawai_ep01"]
    assert episode["candidates"][0]["timeMs"] == 0
    assert episode["candidates"][0]["options"]
    assert episode["publishedNodes"][0]["style"]
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "弹幕内容" not in dumped
    assert "这段太心疼了" not in dumped
    assert "不应进入结果" not in dumped
