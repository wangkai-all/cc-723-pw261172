"""
RINEX 3.05 观测数据接收站 —— FastAPI 入口。

只整理 GNSS 原始观测（值、缺测、LLI/SSI、事件、来源行），不计算定位结果。
"""
from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response

from . import service
from .service import (
    build_csv, epoch_brief, epoch_detail, get_raw_line, obs_dict, store,
)

app = FastAPI(title="RINEX 3.05 观测数据接收站", version="1.0.0")

# 开发期 Vite (5173) 与本地静态页都允许访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/files")
async def upload_file(file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "上传文件为空")
    try:
        stored = store.save(file.filename or "uploaded.06o", raw)
    except Exception as exc:  # 解析级致命错误
        raise HTTPException(422, f"文件无法解析：{exc}") from exc
    r = stored.result
    return {
        "file_id": stored.file_id,
        "filename": stored.filename,
        "systems": r.systems,
        "obs_types": r.obs_types,
        "stats": r.stats,
        "truncated": r.truncated,
        "header": {
            "version": r.header.version,
            "file_type": r.header.file_type,
            "satellite_system": r.header.satellite_system,
            "marker_name": r.header.marker_name,
            "marker_number": r.header.marker_number,
            "receiver_type": r.header.receiver_type,
            "antenna_type": r.header.antenna_type,
            "approx_position": r.header.approx_position,
            "time_system": r.header.time_system,
            "first_observation_time": r.header.first_observation_time,
            "obs_types": r.header.obs_types,
            "obs_types_lines": r.header.obs_types_lines,
            "end_of_header_line": r.header.end_of_header_line,
            "raw_lines": r.header.raw_lines,
        },
        "anomalies": [a.__dict__ for a in r.anomalies],
        "epochs": [epoch_brief(e) for e in r.epochs],
    }


@app.get("/api/files")
def list_files():
    return [
        {
            "file_id": f.file_id,
            "filename": f.filename,
            "epoch_count": len(f.result.epochs),
            "error_count": f.result.stats["anomaly_error_count"],
            "truncated": f.result.truncated,
        }
        for f in store.list()
    ]


def _require(file_id: str):
    try:
        return store.get(file_id)
    except KeyError:
        raise HTTPException(404, f"file_id {file_id} 不存在或已过期")


@app.get("/api/files/{file_id}/summary")
def summary(file_id: str):
    stored = _require(file_id)
    r = stored.result
    return {
        "file_id": file_id,
        "filename": stored.filename,
        "systems": r.systems,
        "obs_types": r.obs_types,
        "stats": r.stats,
        "truncated": r.truncated,
        "header": {
            "version": r.header.version,
            "marker_name": r.header.marker_name,
            "marker_number": r.header.marker_number,
            "receiver_number": r.header.receiver_number,
            "receiver_type": r.header.receiver_type,
            "receiver_version": r.header.receiver_version,
            "antenna_number": r.header.antenna_number,
            "antenna_type": r.header.antenna_type,
            "approx_position": r.header.approx_position,
            "antenna_delta": r.header.antenna_delta,
            "antenna_height": r.header.antenna_height,
            "time_system": r.header.time_system,
            "first_observation_time": r.header.first_observation_time,
            "obs_types": r.header.obs_types,
            "obs_types_lines": r.header.obs_types_lines,
            "end_of_header_line": r.header.end_of_header_line,
            "raw_lines": r.header.raw_lines,
        },
        "anomalies": [a.__dict__ for a in r.anomalies],
    }


@app.get("/api/files/{file_id}/epochs")
def epochs(file_id: str,
           system: str | None = Query(None),
           start: str | None = Query(None, description="起始 ISO 时间，含"),
           end: str | None = Query(None, description="结束 ISO 时间，含")):
    stored = _require(file_id)
    eps = service.filter_epochs(stored, system, start, end)
    return {"count": len(eps), "epochs": [epoch_brief(e) for e in eps]}


@app.get("/api/files/{file_id}/epochs/{epoch_index}")
def epoch(file_id: str, epoch_index: int):
    stored = _require(file_id)
    if not (0 <= epoch_index < len(stored.result.epochs)):
        raise HTTPException(404, "历元序号越界")
    return epoch_detail(stored, epoch_index)


@app.get("/api/files/{file_id}/satellites/{satellite}")
def satellite_history(file_id: str, satellite: str,
                      obs_type: str | None = Query(None)):
    """某颗卫星跨全部历元的观测序列。"""
    stored = _require(file_id)
    out = []
    for ep in stored.result.epochs:
        sat = next((s for s in ep.satellites if s.satellite == satellite), None)
        if sat is None:
            continue
        obs = [obs_dict(o) for o in sat.observations
               if obs_type is None or o.obs_type == obs_type]
        out.append({
            "epoch_index": ep.index,
            "epoch_time": ep.epoch_time,
            "epoch_flag": ep.epoch_flag,
            "line": sat.line,
            "observations": obs,
        })
    if not out:
        raise HTTPException(404, f"卫星 {satellite} 无任何观测记录")
    return {"satellite": satellite, "records": out}


@app.get("/api/files/{file_id}/source-line/{line_no}")
def source_line(file_id: str, line_no: int):
    """数值溯源：返回指定行号的原文与上下文。"""
    stored = _require(file_id)
    lines = stored.raw_text.split("\n")
    if not (1 <= line_no <= len(lines)):
        raise HTTPException(404, "行号越界")
    ctx = []
    for n in range(max(1, line_no - 2), min(len(lines), line_no + 2) + 1):
        ctx.append({"line": n, "text": lines[n - 1], "current": n == line_no})
    return {"line": line_no, "text": get_raw_line(stored, line_no), "context": ctx}


@app.get("/api/files/{file_id}/export")
def export(file_id: str,
           format: str = Query("csv", pattern="^(csv|json)$"),
           system: str | None = Query(None),
           start: str | None = Query(None),
           end: str | None = Query(None)):
    """按系统与时间段导出；CSV 含全部质量标记与来源行，JSON 为结构化结果。"""
    stored = _require(file_id)
    eps = service.filter_epochs(stored, system, start, end)
    if format == "csv":
        csv_text = build_csv(stored, system, start, end)
        fname = f"{os.path.splitext(stored.filename)[0]}_export.csv"
        return Response(
            content="﻿" + csv_text,  # BOM，Excel 正确识别 UTF-8
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition":
                     f"attachment; filename*=UTF-8''{quote(fname)}"},
        )
    payload = {
        "filename": stored.filename,
        "filter": {"system": system, "start": start, "end": end},
        "time_system_note": "时间戳保留文件原始时间系统，未做换算",
        "epochs": [epoch_detail(stored, ep.index) for ep in eps],
    }
    fname = f"{os.path.splitext(stored.filename)[0]}_export.json"
    return Response(
        content=__import__("json").dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition":
                 f"attachment; filename*=UTF-8''{quote(fname)}"},
    )


@app.get("/api/files/{file_id}/report")
def reception_report(file_id: str):
    """接收报告：逐项说明异常位置（行号、历元、卫星、级别）。"""
    stored = _require(file_id)
    r = stored.result
    return {
        "filename": stored.filename,
        "truncated": r.truncated,
        "stats": r.stats,
        "anomalies": [a.__dict__ for a in r.anomalies],
        "legend": {
            "error": "影响数据完整性的结构问题（如截断、未知系统、不支持的时间系统）",
            "warning": "可恢复问题（如字段数不符、坏标记），已按规则处理",
            "info": "需要知悉的正常事件（如头部更新）",
        },
    }


# ---------------------------------------------------------------------- #
# 前端静态页（构建后挂载；开发期可用 Vite dev server）
# ---------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def index():
    idx = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(idx):
        return FileResponse(idx)
    return PlainTextResponse(
        "后端已启动。前端开发：cd frontend && npm install && npm run dev", 200)


if os.path.isdir(STATIC_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
