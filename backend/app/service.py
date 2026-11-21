"""
上传文件的内存存储与解析服务。

只保存 GNSS 原始观测解析结果，不做任何定位解算。
原始文本保留，用于网页展示任意数值对应的原行。
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from threading import Lock

from .parser import ParseResult, parse_rinex_text, LLI_BITS, SSI_LEVELS


@dataclass
class StoredFile:
    file_id: str
    filename: str
    raw_text: str
    result: ParseResult


class FileStore:
    def __init__(self) -> None:
        self._files: dict[str, StoredFile] = {}
        self._lock = Lock()

    def save(self, filename: str, raw: bytes) -> StoredFile:
        # RINEX 文本为 ASCII；容错解码，非法字节以替换符保留并由解析器报异常
        text = raw.decode("ascii", errors="replace")
        result = parse_rinex_text(text, filename)
        file_id = uuid.uuid4().hex[:12]
        stored = StoredFile(file_id, filename, text, result)
        with self._lock:
            self._files[file_id] = stored
        return stored

    def get(self, file_id: str) -> StoredFile:
        with self._lock:
            if file_id not in self._files:
                raise KeyError(file_id)
            return self._files[file_id]

    def list(self) -> list[StoredFile]:
        with self._lock:
            return list(self._files.values())


store = FileStore()


# ---------------------------------------------------------------------- #
# 查询辅助
# ---------------------------------------------------------------------- #
def epoch_brief(ep) -> dict:
    return {
        "index": ep.index,
        "line": ep.line,
        "epoch_time": ep.epoch_time,
        "time_system": ep.time_system,
        "epoch_flag": ep.epoch_flag,
        "flag_meaning": ep.flag_meaning,
        "satellite_count": len(ep.satellites),
        "events": ep.events,
        "truncated": ep.truncated,
        "has_header_update": ep.header_update is not None,
    }


def satellite_brief(sat) -> dict:
    missing = sum(1 for o in sat.observations if o.missing)
    return {
        "satellite": sat.satellite,
        "system": sat.system,
        "line": sat.line,
        "obs_count": len(sat.observations),
        "missing_count": missing,
        "lli_count": sum(1 for o in sat.observations if o.lli is not None),
        "ssi_count": sum(1 for o in sat.observations if o.ssi is not None),
    }


def obs_dict(o) -> dict:
    return {
        "obs_type": o.obs_type,
        "field_index": o.field_index,
        "value": o.value,
        "missing": o.missing,
        "missing_reason": o.missing_reason,
        "lli": o.lli,
        "lli_meaning": _lli_meaning(o.lli),
        "ssi": o.ssi,
        "ssi_meaning": SSI_LEVELS.get(o.ssi) if o.ssi else None,
        "raw_field": o.raw_field,
        "source_line": o.source_line,
    }


def _lli_meaning(lli: str | None) -> list[str] | None:
    if not lli:
        return None
    return [text for bit, text in LLI_BITS.items() if int(lli) & int(bit)]


def get_raw_line(stored: StoredFile, line_no: int) -> str:
    """按 1 基行号取原文（用于数值溯源）。"""
    lines = stored.raw_text.split("\n")
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1]
    return ""


def epoch_detail(stored: StoredFile, epoch_index: int) -> dict:
    ep = stored.result.epochs[epoch_index]
    return {
        **epoch_brief(ep),
        "raw_line": ep.raw_line,
        "clock_offset": ep.clock_offset,
        "obs_types_snapshot": ep.obs_types_snapshot,
        "header_update": ep.header_update,
        "satellites": [
            {
                **satellite_brief(sat),
                "raw_line": sat.raw_line,
                "observations": [obs_dict(o) for o in sat.observations],
            }
            for sat in ep.satellites
        ],
    }


def filter_epochs(stored: StoredFile, system: str | None,
                  start: str | None, end: str | None) -> list:
    """按系统与时间段过滤历元（时间字符串按原始分量的 ISO 形式字典序比较，
    不做任何时间系统换算）。"""
    out = []
    for ep in stored.result.epochs:
        if start and ep.epoch_time < start:
            continue
        if end and ep.epoch_time > end:
            continue
        if system and not any(s.system == system for s in ep.satellites):
            continue
        out.append(ep)
    return out


def build_csv(stored: StoredFile, system: str | None,
              start: str | None, end: str | None) -> str:
    """导出 CSV：每行一个观测字段，含数值、缺测标记、LLI/SSI、来源行。"""
    import csv

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "file", "epoch_index", "epoch_time", "time_system", "epoch_flag",
        "flag_meaning", "system", "satellite", "obs_type", "field_index",
        "value", "missing", "missing_reason", "lli", "ssi", "source_line",
    ])
    for ep in filter_epochs(stored, system, start, end):
        for sat in ep.satellites:
            if system and sat.system != system:
                continue
            for o in sat.observations:
                writer.writerow([
                    stored.filename, ep.index, ep.epoch_time, ep.time_system,
                    ep.epoch_flag, ep.flag_meaning, sat.system, sat.satellite,
                    o.obs_type, o.field_index,
                    "" if o.value is None else f"{o.value:.6f}",
                    "1" if o.missing else "0",
                    o.missing_reason or "", o.lli or "", o.ssi or "",
                    o.source_line,
                ])
    return buf.getvalue()
