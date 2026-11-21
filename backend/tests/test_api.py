"""FastAPI 接口集成测试：上传、查询、溯源、筛选、导出与接收报告。"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app  # noqa: E402
from app.service import store  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "SAMPLE_MIXED_305.06O")
BAD_TS = os.path.join(os.path.dirname(__file__), "..", "samples", "SAMPLE_BAD_TIMESYS_305.06O")


@pytest.fixture()
def client():
    store._files.clear()
    return TestClient(app)


@pytest.fixture()
def file_id(client):
    with open(SAMPLE, "rb") as f:
        resp = client.post(
            "/api/files",
            files={"file": ("SAMPLE_MIXED_305.06O", f.read(), "text/plain")},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["file_id"]


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_upload_returns_station_and_report(client, file_id):
    r = client.get(f"/api/files/{file_id}/summary").json()
    assert r["header"]["marker_name"] == "SAMPLE00"
    assert set(r["systems"]) == {"G", "R", "E", "C"}
    assert r["truncated"] is True
    codes = {a["code"] for a in r["anomalies"]}
    assert "file_truncated" in codes and "header_updated" in codes
    # 每条异常都带行号或可定位信息
    for a in r["anomalies"]:
        assert a["message"]


def test_epoch_detail_with_quality_markers(client, file_id):
    ep = client.get(f"/api/files/{file_id}/epochs/0").json()
    g02 = next(s for s in ep["satellites"] if s["satellite"] == "G02")
    blank = g02["observations"][4]
    assert blank["missing"] is True
    assert blank["missing_reason"] == "blank"
    # 缺测值上的 LLI/SSI 必须单独保留
    assert blank["lli"] == "1" and blank["ssi"] == "1"
    assert blank["value"] is None


def test_source_line_traceability(client, file_id):
    ep = client.get(f"/api/files/{file_id}/epochs/0").json()
    g01 = ep["satellites"][0]
    line_no = g01["observations"][0]["source_line"]
    src = client.get(f"/api/files/{file_id}/source-line/{line_no}").json()
    assert src["text"].startswith("G01")
    assert len(src["text"]) == 259  # 超长行完整保留，未按 80 列截断
    assert len(src["context"]) >= 3


def test_epoch_filter_by_system_and_time(client, file_id):
    r = client.get(
        f"/api/files/{file_id}/epochs",
        params={
            "system": "G",
            "start": "2026-11-22T00:01:00",
            "end": "2026-11-22T00:02:30",
        },
    ).json()
    times = [e["epoch_time"] for e in r["epochs"]]
    assert times == [
        "2026-11-22T00:01:30",
        "2026-11-22T00:02:30",
    ]


def test_export_csv_and_json(client, file_id):
    csv_resp = client.get(
        f"/api/files/{file_id}/export", params={"format": "csv", "system": "R"}
    )
    assert csv_resp.status_code == 200
    rows = csv_resp.text.lstrip("﻿").splitlines()
    assert rows[0].startswith("file,epoch_index,")
    assert all(",R," in row for row in rows[1:])

    json_resp = client.get(f"/api/files/{file_id}/export", params={"format": "json"})
    assert json_resp.status_code == 200
    payload = json_loads(json_resp)
    assert payload["time_system_note"]
    assert len(payload["epochs"]) == 8


def json_loads(resp):
    import json
    return json.loads(resp.content)


def test_report_endpoint(client, file_id):
    rpt = client.get(f"/api/files/{file_id}/report").json()
    assert rpt["truncated"] is True
    trunc = [a for a in rpt["anomalies"] if a["code"] == "file_truncated"]
    assert trunc and trunc[0]["line"] is not None


def test_unsupported_time_system_reported_not_converted(client):
    with open(BAD_TS, "rb") as f:
        resp = client.post(
            "/api/files", files={"file": ("BAD.06O", f.read(), "text/plain")}
        )
    d = resp.json()
    assert any(a["code"] == "unsupported_time_system" for a in d["anomalies"])
    ep = client.get(f"/api/files/{d['file_id']}/epochs/0").json()
    assert ep["time_system"] == "FOO"
    assert ep["epoch_time"] == "2026-11-22T00:00:00"


def test_unknown_file_404(client):
    assert client.get("/api/files/nope/summary").status_code == 404


def test_empty_upload_rejected(client):
    resp = client.post("/api/files", files={"file": ("x.06o", b"", "text/plain")})
    assert resp.status_code == 400


def test_satellite_history(client, file_id):
    r = client.get(f"/api/files/{file_id}/satellites/G01").json()
    assert r["satellite"] == "G01"
    # G01 出现在更新前（16 列）与更新后（8 列）历元中
    field_counts = [len(rec["observations"]) for rec in r["records"]]
    assert 16 in field_counts and 8 in field_counts
