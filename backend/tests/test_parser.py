"""
解析器单元测试：逐项覆盖验收要求中的边界场景。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parser import parse_rinex_text, RinexParseError, Rinex3ObsParser  # noqa: E402

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")
MAIN = os.path.join(SAMPLE_DIR, "SAMPLE_MIXED_305.06O")
BAD_TS = os.path.join(SAMPLE_DIR, "SAMPLE_BAD_TIMESYS_305.06O")


@pytest.fixture(scope="module")
def result():
    with open(MAIN, encoding="ascii") as f:
        return parse_rinex_text(f.read(), "SAMPLE_MIXED_305.06O")


def test_header_continuation_joined(result):
    """头部续行接齐：G 系统头部原始定义 16 个类型跨两行，合并后完整且顺序正确。"""
    assert len(result.header.obs_types["G"]) == 16
    assert result.header.obs_types["G"][0] == "C1C"
    assert result.header.obs_types["G"][-1] == "S2L"
    assert result.header.obs_types_lines["G"] == [8, 9]
    # 其他系统不受 G 续行影响（续行第 0 列必须为空）
    assert len(result.header.obs_types["R"]) == 8
    assert len(result.header.obs_types["E"]) == 13
    assert len(result.header.obs_types["C"]) == 6


def test_different_column_counts_per_system(result):
    """不同系统列数不同，按各自类型数解释字段。"""
    ep0 = result.epochs[0]
    counts = {s.satellite: len(s.observations) for s in ep0.satellites}
    assert counts["G01"] == 16
    assert counts["G02"] == 16
    assert counts["R01"] == 8
    assert counts["E01"] == 13


def test_long_line_not_split_at_80(result):
    """超过 80 字符的卫星行按完整长行读取（最长 259 列，16 字段）。"""
    g01 = result.epochs[0].satellites[0]
    assert len(g01.raw_line) == 259
    assert len(g01.observations) == 16
    # 数值按 16 列固定宽度逐字段对齐，而不是 RINEX2 的拼接
    assert g01.observations[0].value == pytest.approx(20123.456)
    assert g01.observations[15].obs_type == "S2L"


def test_legal_trailing_omission_not_truncation(result):
    """合法尾部省略：E01 只给 10/13 字段，补成缺测但历元不截断。"""
    e01 = next(s for s in result.epochs[0].satellites if s.satellite == "E01")
    assert len(e01.observations) == 13
    tail = e01.observations[10:]
    assert all(o.missing and o.missing_reason == "trailing_omission" for o in tail)
    assert result.epochs[0].truncated is False


def test_no_pull_from_next_satellite_or_epoch(result):
    """尾部省略绝不拿同历元下一颗卫星或下一历元的行补齐。"""
    ep0 = result.epochs[0]
    e01 = next(s for s in ep0.satellites if s.satellite == "E01")
    # 省略字段没有原文、来源行仍属于 E01 自己
    assert e01.observations[12].raw_field == ""
    assert e01.observations[12].source_line == e01.line
    # 下一颗卫星/下一历元未被消费：ep0 仍有 4 颗，ep1 完整
    assert [s.satellite for s in ep0.satellites] == ["G01", "G02", "R01", "E01"]
    assert len(result.epochs[1].satellites) == 4


def test_real_truncation_detected(result):
    """真正截断：最后历元声明 3 星只给 2 行即 EOF，判 error 且不拼补。"""
    last = result.epochs[-1]
    assert last.truncated is True
    assert len(last.satellites) == 2
    codes = [a.code for a in result.anomalies if a.line == last.line]
    assert "file_truncated" in codes
    assert result.truncated is True


def test_epoch_flags_events(result):
    """历元标志区分正常、事件与头部变化。"""
    flags = [e.epoch_flag for e in result.epochs]
    assert flags == [0, 0, 1, 0, 4, 0, 5, 0]
    power_on = result.epochs[2]
    assert power_on.epoch_flag == 1 and power_on.satellites == []
    external = result.epochs[6]
    assert external.epoch_flag == 5 and external.satellites == []


def test_header_update_only_affects_later(result):
    """flag=4 头部更新：G 由 16 类型变 8，只对之后历元生效。"""
    upd = result.epochs[4]
    assert upd.epoch_flag == 4 and upd.header_update is not None
    change = upd.header_update["changes"][0]
    assert change["system"] == "G"
    assert len(change["previous"]) == 16 and len(change["obs_types"]) == 8
    # 更新前的历元快照仍是 16
    assert len(result.epochs[3].obs_types_snapshot["G"]) == 16
    # 更新后的历元快照是 8
    after = result.epochs[5]
    assert len(after.obs_types_snapshot["G"]) == 8
    g01 = next(s for s in after.satellites if s.satellite == "G01")
    assert len(g01.observations) == 8
    # 更新后的合法尾部省略按新列数解释
    g03 = next(s for s in after.satellites if s.satellite == "G03")
    assert [o.missing_reason for o in g03.observations[6:]] == [
        "trailing_omission", "trailing_omission"]


def test_lli_ssi_stored_separately(result):
    """LLI/SSI 与数值分开存储；缺测值上的标记也保留。"""
    g02 = next(s for s in result.epochs[0].satellites if s.satellite == "G02")
    first = g02.observations[0]
    assert first.value == pytest.approx(20987.111)
    assert first.lli == "1" and first.ssi == "3"
    # 第 5 字段全空缺测，但 LLI/SSI 仍在
    blank = g02.observations[4]
    assert blank.missing and blank.value is None
    assert blank.lli == "1" and blank.ssi == "1"


def test_zero_and_blank_are_missing_not_value(result):
    """0.0 空值与全空字段都按缺测处理，不并入测量数值。"""
    c01 = next(s for s in result.epochs[1].satellites if s.satellite == "C01")
    by_type = {o.obs_type: o for o in c01.observations}
    assert by_type["L1I"].missing and by_type["L1I"].missing_reason == "zero_blank"
    assert by_type["S1I"].missing and by_type["S1I"].missing_reason == "blank"
    assert by_type["C1I"].value == pytest.approx(39000.0)


def test_source_line_preserved(result):
    """每个数值都能回溯到原行与行号。"""
    g01 = result.epochs[0].satellites[0]
    assert g01.line == 16
    assert all(o.source_line == 16 for o in g01.observations)
    assert g01.observations[0].raw_field.startswith("     20123.456")


def test_unsupported_time_system_reported_only():
    """不支持的时间系统：报 error 但不换算，时间分量原样保留。"""
    with open(BAD_TS, encoding="ascii") as f:
        r = parse_rinex_text(f.read(), "BAD_TS")
    assert r.header.time_system == "FOO"
    assert any(a.code == "unsupported_time_system" and a.severity == "error"
               for a in r.anomalies)
    ep = r.epochs[0]
    assert ep.time_system == "FOO"
    assert ep.epoch_time == "2026-11-22T00:00:00"


def test_receiver_report_lists_each_anomaly_with_line(result):
    """接收报告逐项、带行号说明异常位置。"""
    trunc = [a for a in result.anomalies if a.code == "file_truncated"]
    assert trunc and all(a.line is not None for a in trunc)
    upd = [a for a in result.anomalies if a.code == "header_updated"]
    assert upd and upd[0].line == 29


def test_empty_file_raises():
    with pytest.raises(RinexParseError):
        parse_rinex_text("", "empty")


def test_missing_end_of_header():
    bad = "     3.05           OBSERVATION DATA    M                   " \
          "RINEX VERSION / TYPE\n"
    r = parse_rinex_text(bad, "bad")
    assert any(a.code == "missing_end_of_header" for a in r.anomalies)


def test_unexpected_line_never_joined(tmp_path):
    """数据体中的坏行只报错跳过，绝不与相邻卫星行拼接。"""
    with open(MAIN, encoding="ascii") as f:
        lines = f.read().split("\n")
    # 在第一条卫星行后插入一行垃圾
    assert lines[15].startswith("G01")
    lines.insert(16, "GARBAGE LINE WITHOUT LABEL")
    r = parse_rinex_text("\n".join(lines), "garbage")
    bad = [a for a in r.anomalies if a.code == "unexpected_line"]
    assert bad and bad[0].line == 17
    # G01 本身仍是完整 16 字段，未受污染
    g01 = r.epochs[0].satellites[0]
    assert g01.satellite == "G01" and len(g01.observations) == 16


def test_epoch_truncated_when_next_epoch_comes_early():
    """下一历元提前出现：当前历元判截断，且不消费下一历元的行。"""
    with open(MAIN, encoding="ascii") as f:
        lines = f.read().split("\n")
    # 删掉 ep0 的最后一颗卫星行 E01（行号 19，0 基 18）
    assert lines[18].startswith("E01")
    del lines[18]
    r = parse_rinex_text("\n".join(lines), "early")
    ep0 = r.epochs[0]
    assert ep0.truncated
    assert any(a.code == "epoch_truncated" for a in r.anomalies
               if a.epoch == ep0.epoch_time)
    # 下一历元仍被独立解析
    assert result_epoch_time(r, 1) == "2026-11-22T00:00:30"


def result_epoch_time(r, i):
    return r.epochs[i].epoch_time
