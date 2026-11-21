#!/usr/bin/env python3
"""
生成 RINEX 3.05 观测数据样例文件（确定性，无随机数）。

样例覆盖验收要求的全部边界场景：
  1. 多系统且各系统观测类型列数不同（G=16 / R=8 / E=13 / C=6）
  2. 超过 80 字符的卫星观测长行（16 字段 × 16 列 + 3 = 259 列）
  3. SYS / # / OBS TYPES 头部续行（G 的 16 个类型超过首行 13 槽位）
  4. 合法尾部省略（E01 只给 10/13 个字段；更新后 G03 只给 6/8 个）
  5. flag=4 头部更新（G 系统类型由 16 变 8，只影响之后历元）
  6. 真正截断的历元（最后一个历元声明 3 星只给 2 行即 EOF）
  7. 事件历元（flag=1 开机、flag=5 外部事件）
  8. LLI 丢锁标记、SSI 信号强度标记、空字段、0.0 缺测字段
  9. 独立文件演示不支持的时间系统（FOO，只报告不换算）
"""
from __future__ import annotations

import os

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "backend", "samples")

G_TYPES = ["C1C", "L1C", "D1C", "S1C", "C1W", "L1W", "D1W", "S1W",
           "C2W", "L2W", "D2W", "S2W", "C2L", "L2L", "D2L", "S2L"]  # 16 个，强制续行
R_TYPES = ["C1C", "L1C", "D1C", "C2C", "L2C", "D2C", "C2P", "L2P"]  # 8 个
E_TYPES = ["C1C", "L1C", "D1C", "S1C", "C6A", "L6A", "D6A", "S6A",
           "C7I", "L7I", "D7I", "S7I", "C8X"]                        # 13 个，恰好占满首行
C_TYPES = ["C1I", "L1I", "D1I", "S1I", "C7I", "L7I"]                # 6 个

G_TYPES_AFTER_UPDATE = ["C1C", "L1C", "D1C", "S1C",
                        "C2W", "L2W", "D2W", "S2W"]                  # 更新后 8 个


def hdr(text: str, label: str) -> str:
    # 标签严格占列 61-80（0 基 60:80），整行补齐到至少 80 列
    return f"{text:<60}{label:<20}"[:80].ljust(80)


def obs_types_header(system: str, types: list[str]) -> list[str]:
    """生成 SYS / # / OBS TYPES 行，超过 13 个自动产生续行。

    首行布局：列1 系统字母、列4-6 数量、列8 起每 4 列一个 3 字符类型（13 个）。
    续行布局：列1-3 留空，列5（0 基 offset 4）起每 4 列一个类型（14 个）。
    """
    lines = []
    # 列1 系统字母、列4-6 数量、列7（0 基 offset 6）起每 4 列一个类型，首行 13 个
    first = f"{system} {len(types):>3d}".ljust(6)
    first += "".join(f"{t:<4}" for t in types[:13])
    lines.append(hdr(first, "SYS / # / OBS TYPES"))
    rest = types[13:]
    # 续行：列1-6 留空，类型同样从列7（0 基 offset 6）起，每 4 列一个
    for chunk_start in range(0, len(rest), 13):
        chunk = rest[chunk_start:chunk_start + 13]
        cont = " " * 6 + "".join(f"{t:<4}" for t in chunk)
        lines.append(hdr(cont, "SYS / # / OBS TYPES"))
    return lines


def epoch_line(hh, mm, ss, flag, nsat) -> str:
    """RINEX 3.05 历元行（表 A-3）严格列宽，0 基偏移：
    0:'>' 2-5 年 7-8 月 10-11 日 13-14 时 16-17 分 19-28 秒(10列)
    31 历元标志、32-34 卫星数（标准 %3i，列33-35）、41-55 钟偏。
    """
    return (
        ">"
        f" {2026:4d} {11:02d} {22:02d} {hh:02d} {mm:02d} {ss:10.7f}"
        f"  {flag:1d}{nsat:3d}"
    )


def field(value, lli: str = " ", ssi: str = " ") -> str:
    """单个 16 列观测字段：14 列数值 + LLI + SSI。"""
    if value is None:
        num = " " * 14
    else:
        num = f"{value:14.3f}"
    return f"{num}{lli}{ssi}"


def blank_field(lli: str = " ", ssi: str = " ") -> str:
    return f"{'':14s}{lli}{ssi}"


def sat_line(sat: str, fields: list[str]) -> str:
    return f"{sat:<3s}" + "".join(fields)


def base_header(time_sys: str = "GPS") -> list[str]:
    lines = [
        # 版本占列1-9(0:9)、类型 O 在列21(0基20)、系统 M 在列41(0基40)
        hdr("3.05".ljust(20) + "O".ljust(20) + "M",
            "RINEX VERSION / TYPE"),
        hdr("SAMPLE00", "MARKER NAME"),
        hdr("R-00001", "MARKER NUMBER"),
        hdr("RCV-001         TRIMBLE ALLOY          5.4.2", "REC # / TYPE / VERS"),
        hdr("ANT-001         TRM57971.00 NONE", "ANT # / TYPE"),
        hdr("  3872345.6789  1023456.1234  4936234.5678", "APPROX POSITION XYZ"),
        hdr("        0.0000        0.0000        0.0000", "ANTENNA: DELTA H/E/N"),
    ]
    lines += obs_types_header("G", G_TYPES)
    lines += obs_types_header("R", R_TYPES)
    lines += obs_types_header("E", E_TYPES)
    lines += obs_types_header("C", C_TYPES)
    lines.append(hdr("  2026    11    22     0     0    0.0000000     " + time_sys,
                     "TIME OF FIRST OBS"))
    lines.append(hdr("", "END OF HEADER"))
    return lines


def build_main_sample() -> str:
    lines = base_header("GPS")

    # ---- 历元 1：正常观测，4 星；G01 全 16 字段（259 列超长行） ----
    lines.append(epoch_line(0, 0, 0, 0, 4))
    g01 = [field(20123.456 + i * 0.01, ssi=str(1 + i % 5)) for i in range(16)]
    lines.append(sat_line("G01", g01))
    # G02：含 LLI 丢锁标记、SSI、空字段（第 5 字段全空但保留标记位）
    g02 = [field(20987.111, lli="1", ssi="3"),
           field(112233.444, lli="1", ssi="3"),
           field(-345.678),
           field(43.210, ssi="2"),
           blank_field(lli="1", ssi="1"),          # 全空缺测，LLI/SSI 仍保留
           field(20555.000),
           field(110999.000),
           field(12.345)]
    g02 += [field(100.0 + i) for i in range(8)]   # 补齐 16 个
    lines.append(sat_line("G02", g02))
    # R01：R 系统 8 列
    lines.append(sat_line("R01", [field(18000.0 + i * 1.5, ssi="4") for i in range(8)]))
    # E01：只给 10/13 个字段 —— 合法尾部省略，绝不能判截断
    lines.append(sat_line("E01", [field(19500.0 + i * 2.25) for i in range(10)]))

    # ---- 历元 2：正常观测，含 0.0 空值字段 ----
    lines.append(epoch_line(0, 0, 30, 0, 4))
    lines.append(sat_line("G01", [field(20124.0 + i * 0.01) for i in range(16)]))
    lines.append(sat_line("G02", [field(20990.0 + i) for i in range(16)]))
    lines.append(sat_line("R01", [field(18010.0 + i) for i in range(8)]))
    c01 = [field(39000.0), field(0.0), field(250.0),   # 0.0 按 RINEX 规则视为缺测
           blank_field(), field(38950.0), field(99.9)]
    lines.append(sat_line("C01", c01))

    # ---- 历元 3：flag=1 开机事件，无卫星记录 ----
    lines.append(epoch_line(0, 1, 0, 1, 0))

    # ---- 历元 4：正常观测 ----
    lines.append(epoch_line(0, 1, 30, 0, 2))
    lines.append(sat_line("G01", [field(20130.0 + i * 0.01) for i in range(16)]))
    lines.append(sat_line("R02", [field(17500.0 + i) for i in range(8)]))

    # ---- 历元 5：flag=4 头部更新（G 系统 16 -> 8 类型），更新块之后生效 ----
    lines.append(epoch_line(0, 2, 0, 4, 0))
    lines += obs_types_header("G", G_TYPES_AFTER_UPDATE)

    # ---- 历元 6：更新后的首个历元，按 8 列解释 G ----
    lines.append(epoch_line(0, 2, 30, 0, 2))
    lines.append(sat_line("G01", [field(20200.0 + i) for i in range(8)]))
    # G03 只给 6/8 个字段：更新定义下的合法尾部省略
    lines.append(sat_line("G03", [field(20700.0 + i) for i in range(6)]))

    # ---- 历元 7：flag=5 外部事件 ----
    lines.append(epoch_line(0, 3, 0, 5, 0))

    # ---- 历元 8：真正截断 —— 声明 3 颗卫星，只给 2 行后文件结束 ----
    lines.append(epoch_line(0, 3, 30, 0, 3))
    lines.append(sat_line("G01", [field(20300.0 + i) for i in range(8)]))
    lines.append(sat_line("G02", [field(20800.0 + i) for i in range(8)]))
    # 故意 EOF：第三条 G03 记录缺失

    return "\n".join(lines) + "\n"


def build_bad_timesys_sample() -> str:
    """不支持的时间系统 FOO：解析器只报告、不换算。"""
    lines = base_header("FOO")
    lines.append(epoch_line(0, 0, 0, 0, 1))
    lines.append(sat_line("G01", [field(20123.456 + i * 0.01) for i in range(16)]))
    return "\n".join(lines) + "\n"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    main_path = os.path.join(OUT_DIR, "SAMPLE_MIXED_305.06O")
    bad_path = os.path.join(OUT_DIR, "SAMPLE_BAD_TIMESYS_305.06O")
    with open(main_path, "w", encoding="ascii", newline="\n") as f:
        f.write(build_main_sample())
    with open(bad_path, "w", encoding="ascii", newline="\n") as f:
        f.write(build_bad_timesys_sample())

    # 自检：打印最长行长度，证明存在超过 80 字符的观测行
    longest = max(len(l) for l in build_main_sample().splitlines())
    print(f"wrote {main_path}")
    print(f"wrote {bad_path}")
    print(f"longest line length = {longest} (RINEX2 续行阈值 = 80)")


if __name__ == "__main__":
    main()
