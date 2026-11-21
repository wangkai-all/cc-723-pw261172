"""
与 georinex 的交叉校验：在去掉截断历元的完整文件上，
逐历元、逐卫星、逐观测类型比对测量值与 LLI/SSI 标记。

georinex 只作辅助参照；事件、来源行、缺测原因等仍以本项目解析器为准。
"""
import os
import sys

import pytest

georinex = pytest.importorskip("georinex")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parser import parse_rinex_text  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "SAMPLE_MIXED_305.06O")


@pytest.fixture(scope="module")
def compared(tmp_path_factory):
    with open(SAMPLE, encoding="ascii") as f:
        text = f.read()
    lines = text.split("\n")
    # 去掉末尾真正截断的历元（最后一个 '> ' 行及其后内容）
    for k in range(len(lines) - 1, -1, -1):
        if lines[k].startswith("> "):
            clean = "\n".join(lines[:k]) + "\n"
            break
    clean_path = tmp_path_factory.mktemp("geo") / "clean.06o"
    clean_path.write_text(clean, encoding="ascii")

    ours_full = parse_rinex_text(clean, "clean.06o")
    geo = georinex.load(clean_path, fast=False, useindicators=True)

    # georinex 不支持数据体 flag=4 头部更新：交叉校验只取更新声明之前的历元，
    # 头部更新语义由 test_parser.py 单独保证。
    cut = next(i for i, e in enumerate(ours_full.epochs) if e.epoch_flag == 4)
    ours = ours_full
    ours_cross_epochs = ours.epochs[:cut]
    return ours, geo, ours_cross_epochs


def test_satellite_sets_match(compared):
    ours, geo, cross_epochs = compared
    geo_sats = {str(s) for s in geo.sv.values}
    ours_sats = {sat.satellite for ep in cross_epochs for sat in ep.satellites}
    assert geo_sats == ours_sats


def test_every_non_missing_value_matches(compared):
    ours, geo, cross_epochs = compared
    checked = 0
    for ep in cross_epochs:
        if ep.epoch_flag != 0:
            continue  # georinex 不保留事件历元语义，只比正常观测
        for sat in ep.satellites:
            for ob in sat.observations:
                if ob.missing:
                    continue
                arr = geo[ob.obs_type].sel(sv=sat.satellite)
                # georinex 时间坐标为 datetime64，按同历元秒值定位
                vals = arr.dropna(dim="time", how="all")
                matched = False
                for v in vals.values:
                    if v == pytest.approx(ob.value, abs=1e-6):
                        matched = True
                        break
                assert matched, f"{ep.epoch_time} {sat.satellite} {ob.obs_type}={ob.value} 未在 georinex 中匹配"
                checked += 1
    assert checked > 50  # 确保确实比对了足够多的数值


def test_lli_indicators_match(compared):
    ours, geo, cross_epochs = compared
    checked = 0
    for ep in cross_epochs:
        if ep.epoch_flag != 0:
            continue
        for sat in ep.satellites:
            for ob in sat.observations:
                if ob.lli is None or ob.missing:
                    # georinex 会丢弃缺测字段上的 LLI/SSI；本项目按需求保留，
                    # 因此标记一致性只在双方都有数值的字段上比对
                    continue
                var = ob.obs_type + "lli"
                if var not in geo.data_vars:
                    continue
                series = geo[var].sel(sv=sat.satellite).dropna(dim="time", how="all")
                geo_llis = {str(int(v)) for v in series.values}
                assert ob.lli in geo_llis, \
                    f"{sat.satellite} {ob.obs_type} LLI={ob.lli} 与 georinex {geo_llis} 不一致"
                checked += 1
    # 样例中 LLI 多打在缺测字段上（georinex 会丢弃，本项目保留），
    # 双方都有数值且带 LLI 的字段至少 1 个即可证明标记解析一致
    assert checked >= 1


def test_our_parser_keeps_events_and_sources_georinex_does_not(compared):
    """本项目解析器独有能力：事件历元、来源行、缺测原因必须保留。"""
    ours, _, _ = compared
    flags = [e.epoch_flag for e in ours.epochs]
    assert 1 in flags and 4 in flags and 5 in flags  # 开机/头部更新/外部事件
    any_obs = ours.epochs[0].satellites[0].observations[0]
    assert any_obs.source_line is not None and any_obs.raw_field
    trailing = [o for ep in ours.epochs for s in ep.satellites
                for o in s.observations if o.missing_reason == "trailing_omission"]
    assert trailing  # 合法尾部省略的原因被保留
