"""
RINEX 3.05 观测数据文件（OBSERVATION DATA, *.*O）解析器。

设计原则（对应验收要求）：
1. 严格按 RINEX 3 的记录格式：历元行一行、每颗卫星一条完整长行，
   每个观测字段固定 16 列（值 14 + LLI 1 + SSI 1）；
   绝不套用 RINEX 2 的 80 字符物理续行拼接。
2. 按“当前生效”的系统观测类型数解释字段；尾部合法省略的缺测
   （RINEX 3 允许卫星行尾部观测为空）按缺测补齐，绝不用下一颗卫星
   或下一历元的行来拼补。
3. 历元标志区分正常观测(0)、事件(1/2/3/5/6) 与头部变化(4)；
   flag=4 的头部更新只作用于其后的记录。
4. LLI（丢锁标记）、SSI（信号强度标记）与缺测值单独存储，
   不并入测量数值；测量值为 null 时仍保留标记。
5. 不支持的时间系统只报告、不换算，时间戳保留原始分量。
6. 保留每行原文与行号，网页可回溯任意数值的来源行。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

# RINEX 3.05 认可的 GNSS 系统标识
KNOWN_SYSTEMS = {"G", "R", "E", "C", "J", "I", "S"}

# RINEX 3.05 表 5-2 的时间系统标识
KNOWN_TIME_SYSTEMS = {"GPS", "GLO", "GAL", "QZS", "BDT", "IRN", "GST"}

# RINEX 3.05 历元标志含义
EPOCH_FLAGS = {
    0: "正常观测",
    1: "上电/新站点开机（前置历元可能缺失）",
    2: "开始移动天线",
    3: "新站点（天线移动后重新静止）",
    4: "头部信息后续发生变化",
    5: "其他外部事件",
    6: "历元标志保留（本解析器按事件处理）",
}

# LLI 各 bit 含义（RINEX 3.05 表 5-7，可组合）
LLI_BITS = {
    "1": "失锁/周跳（可能发生）",
    "2": "半周模糊度",
    "4": "站点无供电（天线悬空）",
}

# SSI 信号强度等级（RINEX 3.05 表 5-8）
SSI_LEVELS = {
    "1": "极差",
    "2": "较差",
    "3": "一般",
    "4": "良好",
    "5": "优秀",
}

SATELLITE_RE = re.compile(r"^([GRECJIS])(\d{2})$")
EPOCH_RE = re.compile(r"^>\s")


@dataclass
class Anomaly:
    """解析中发现的全部异常/事件，逐项带行号。"""
    line: Optional[int]
    code: str
    severity: str          # error | warning | info
    message: str
    epoch: Optional[str] = None
    satellite: Optional[str] = None


@dataclass
class ObsValue:
    """单个观测字段：数值与质量标记分开存储。"""
    obs_type: str
    value: Optional[float]          # 缺测/不可解析时为 None
    lli: Optional[str] = None       # 丢锁标记，原始单字符（'0'..'7' 组合位）
    ssi: Optional[str] = None       # 信号强度标记，原始单字符
    missing: bool = False           # 是否缺测（含全空字段、0.0 空值、尾部省略）
    missing_reason: Optional[str] = None  # blank | zero_blank | trailing_omission | unparseable
    field_index: int = 0            # 该系统观测类型列表中的序号（从 0 起）
    raw_field: str = ""             # 该 16 列原始文本
    source_line: Optional[int] = None


@dataclass
class SatelliteRecord:
    satellite: str
    system: str
    line: int
    raw_line: str
    observations: list[ObsValue] = field(default_factory=list)


@dataclass
class Epoch:
    index: int
    line: int                       # 历元行（'> ' 开头）行号
    raw_line: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: float
    time_system: str
    epoch_flag: int
    flag_meaning: str
    clock_offset: Optional[float]
    epoch_time: str                 # 原始分量拼成的 ISO 风格字符串，不做时区换算
    satellites: list[SatelliteRecord] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    # 该历元生效的观测定义快照（系统 -> 观测类型列表），头部更新后自动变化
    obs_types_snapshot: dict[str, list[str]] = field(default_factory=dict)
    # flag=4 的头部更新明细，挂在该历元上；对之后历元生效
    header_update: Optional[dict] = None
    truncated: bool = False


@dataclass
class HeaderInfo:
    version: Optional[float] = None
    file_type: Optional[str] = None
    satellite_system: Optional[str] = None
    marker_name: Optional[str] = None
    marker_number: Optional[str] = None
    receiver_number: Optional[str] = None
    receiver_type: Optional[str] = None
    receiver_version: Optional[str] = None
    antenna_number: Optional[str] = None
    antenna_type: Optional[str] = None
    approx_position: Optional[list[float]] = None
    antenna_delta: Optional[list[float]] = None
    antenna_height: Optional[float] = None
    first_observation_time: Optional[list] = None   # 6 个原始分量 + 时间系统
    time_system: Optional[str] = None
    # 系统 -> 观测类型列表（头部续行合并后的最终结果）
    obs_types: dict[str, list[str]] = field(default_factory=dict)
    # 观测类型定义在头部出现的行号范围（含续行），供网页展示
    obs_types_lines: dict[str, list[int]] = field(default_factory=dict)
    raw_lines: list[dict] = field(default_factory=list)  # {line, text, label}
    end_of_header_line: Optional[int] = None


@dataclass
class ParseResult:
    filename: str
    header: HeaderInfo
    epochs: list[Epoch]
    anomalies: list[Anomaly]
    systems: list[str]
    obs_types: dict[str, list[str]]
    stats: dict
    truncated: bool

    def to_dict(self) -> dict:
        return asdict(self)


class RinexParseError(Exception):
    """文件级致命错误（如根本不是 RINEX OBS 文件）。"""


def _format_epoch_time(y, mo, d, h, mi, s) -> str:
    """把历元原始时间分量格式化为字符串，秒保留小数、不做任何时区换算。"""
    if float(s).is_integer():
        sec_str = f"{int(s):02d}"
    else:
        sec_str = f"{float(s):09.6f}".rstrip("0")
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}T{int(h):02d}:{int(mi):02d}:{sec_str}"


class Rinex3ObsParser:
    def __init__(self, text: str, filename: str = "<memory>"):
        # 保留原始行（包括空行），行号从 1 起；只去掉行尾换行，不动行内空格
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        self.filename = filename
        self.header = HeaderInfo()
        self.anomalies: list[Anomaly] = []
        self.epochs: list[Epoch] = []
        self._cur_obs_types: dict[str, list[str]] = {}
        self._cur_obs_lines: dict[str, list[int]] = {}
        self._header_update_no = 0

    # ------------------------------------------------------------------ #
    # 公共入口
    # ------------------------------------------------------------------ #
    def parse(self) -> ParseResult:
        if not self.lines:
            raise RinexParseError("文件为空")
        self._parse_header()
        self._parse_body()
        self._finalize_stats()
        systems = sorted(self._cur_obs_types.keys())
        truncated = any(a.code == "file_truncated" for a in self.anomalies)
        return ParseResult(
            filename=self.filename,
            header=self.header,
            epochs=self.epochs,
            anomalies=self.anomalies,
            systems=systems,
            obs_types={k: list(v) for k, v in self._cur_obs_types.items()},
            stats=self._stats,
            truncated=truncated,
        )

    # ------------------------------------------------------------------ #
    # 头部
    # ------------------------------------------------------------------ #
    def _parse_header(self):
        found_end = False
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            lineno = i + 1
            label = line[60:80].strip() if len(line) >= 60 else ""
            self.header.raw_lines.append({"line": lineno, "text": line, "label": label})

            if label == "RINEX VERSION / TYPE":
                try:
                    self.header.version = float(line[0:9].strip())
                except ValueError:
                    self._anom(lineno, "bad_header_field", "error",
                               "RINEX 版本号无法解析: %r" % line[0:9].strip())
                self.header.file_type = line[20:21].strip() or None
                self.header.satellite_system = line[40:41].strip() or None
                if self.header.version is not None and not (3.0 <= self.header.version < 4.0):
                    self._anom(lineno, "unsupported_version", "warning",
                               f"声明 RINEX 版本 {self.header.version}，本解析器按 3.05 规则解释，"
                               "低版本文件的 80 字符续行规则不适用")
                if self.header.file_type and self.header.file_type != "O":
                    self._anom(lineno, "not_observation_file", "error",
                               f"文件类型为 {self.header.file_type!r}，不是观测数据文件(O)")

            elif label == "MARKER NAME":
                self.header.marker_name = line[0:60].strip() or None
            elif label == "MARKER NUMBER":
                self.header.marker_number = line[0:60].strip() or None
            elif label == "REC # / TYPE / VERS":
                self.header.receiver_number = line[0:20].strip() or None
                self.header.receiver_type = line[20:40].strip() or None
                self.header.receiver_version = line[40:60].strip() or None
            elif label == "ANT # / TYPE":
                self.header.antenna_number = line[0:20].strip() or None
                self.header.antenna_type = line[20:40].strip() or None
            elif label == "APPROX POSITION XYZ":
                vals = self._three_floats(line, lineno, label)
                if vals is None:
                    self._anom(lineno, "bad_header_field", "warning",
                               "APPROX POSITION XYZ 三个坐标分量无法解析")
                self.header.approx_position = vals
            elif label == "ANTENNA: DELTA H/E/N":
                vals = self._three_floats(line, lineno, label)
                if vals is None:
                    self._anom(lineno, "bad_header_field", "warning",
                               "ANTENNA: DELTA H/E/N 三个分量无法解析")
                if vals is not None:
                    self.header.antenna_delta = vals
                    self.header.antenna_height = vals[0]
            elif label == "TIME OF FIRST OBS":
                self._parse_first_obs(line, lineno)
            elif label == "SYS / # / OBS TYPES":
                last = self._parse_obs_types_header(i, line, lineno)
                i = last + 1
                continue
            elif label == "END OF HEADER":
                self.header.end_of_header_line = lineno
                found_end = True
                i += 1
                break
            i += 1

        if not found_end:
            self._anom(None, "missing_end_of_header", "error",
                       "未找到 END OF HEADER，头部不完整")
            return
        if not self._cur_obs_types:
            self._anom(None, "missing_obs_types", "error",
                       "头部缺少 SYS / # / OBS TYPES，无法解释任何观测字段")
        self.header.obs_types = {k: list(v) for k, v in self._cur_obs_types.items()}
        self.header.obs_types_lines = {k: list(v) for k, v in self._cur_obs_lines.items()}
        self._body_start = i

    def _parse_obs_types_header(self, i: int, first_line: str, lineno: int) -> int:
        """解析 SYS / # / OBS TYPES 及其续行（续行前 60 列接续类型列表）。"""
        system = first_line[0:1].strip()
        if system not in KNOWN_SYSTEMS:
            self._anom(lineno, "unknown_system", "error",
                       f"观测类型定义中出现未知系统标识 {system!r}")
        try:
            declared = int(first_line[3:6].strip())
        except ValueError:
            self._anom(lineno, "bad_header_field", "error",
                       "SYS / # / OBS TYPES 观测类型数量无法解析")
            declared = -1

        types: list[str] = []
        span = [lineno]
        # 首行（RINEX 3.05 表 A-6）：系统字母列1、数量列4-6、
        # 类型从列7（0 基 offset 6）起，每个槽位 4 列（列7-10、11-14…），共 13 个
        for off in range(6, 58, 4):
            t = first_line[off:off + 3].strip()
            if t:
                types.append(t)
        # 续行：标签相同且第 0 列系统位为空（RINEX 3 规定续行不留系统字母）
        # 类型同样从列7（0 基 offset 6）起，每 4 列一个，最多 13 个
        j = i + 1
        while j < len(self.lines):
            nxt = self.lines[j]
            nxt_label = nxt[60:80].strip() if len(nxt) >= 60 else ""
            if nxt_label != "SYS / # / OBS TYPES" or nxt[0:1].strip() != "":
                break
            span.append(j + 1)
            self.header.raw_lines.append({"line": j + 1, "text": nxt, "label": nxt_label})
            for off in range(6, 58, 4):
                t = nxt[off:off + 3].strip()
                if t:
                    types.append(t)
            j += 1

        if declared >= 0 and len(types) != declared:
            self._anom(lineno, "obs_type_count_mismatch", "warning",
                       f"系统 {system} 声明 {declared} 个观测类型，实际列出 {len(types)} 个，"
                       "按实际列出的类型解释")
        if system:
            self._cur_obs_types[system] = types
            self._cur_obs_lines[system] = span
        return j - 1  # 最后消费的 0 基下标；调用方负责 +1

    def _parse_first_obs(self, line: str, lineno: int):
        parts = line[0:60].split()
        try:
            comps = [int(parts[0]), int(parts[1]), int(parts[2]),
                     int(parts[3]), int(parts[4]), float(parts[5])]
        except (ValueError, IndexError):
            self._anom(lineno, "bad_header_field", "error",
                       "TIME OF FIRST OBS 时间分量无法解析: %r" % line[0:60].strip())
            return
        tsys = parts[6] if len(parts) > 6 else ""
        self.header.first_observation_time = comps + [tsys]
        self.header.time_system = tsys or None
        if tsys and tsys not in KNOWN_TIME_SYSTEMS:
            # 不支持的时间系统：只报告，不擅自换算
            self._anom(lineno, "unsupported_time_system", "error",
                       f"不支持的时间系统 {tsys!r}；时间戳按文件原始分量保留，不做任何换算")

    @staticmethod
    def _three_floats(line: str, lineno: Optional[int], what: str):
        parts = line[0:60].split()
        try:
            return [float(parts[0]), float(parts[1]), float(parts[2])]
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------ #
    # 数据体
    # ------------------------------------------------------------------ #
    def _parse_body(self):
        i = getattr(self, "_body_start", 0)
        n = len(self.lines)
        while i < n:
            line = self.lines[i]
            lineno = i + 1

            if not line.strip():
                i += 1  # 空行跳过
                continue

            if EPOCH_RE.match(line):
                epoch, i = self._parse_epoch(i)
                self.epochs.append(epoch)
                continue

            # 数据体中出现非历元行：属于结构异常。
            # 绝不把它当作上一颗卫星的续行拼接（RINEX 3 无 80 列续行）。
            self._anom(lineno, "unexpected_line", "error",
                       "数据体中出现无法识别的行（已跳过，未与相邻行拼接）: %r"
                       % line[:40])
            i += 1

    def _parse_epoch(self, i: int) -> tuple[Epoch, int]:
        line = self.lines[i]
        lineno = i + 1
        n = len(self.lines)
        comps = line.split()
        # 形如: > 2026 11 22 00 00 00.0000000  0 12
        try:
            year, month, day = int(comps[1]), int(comps[2]), int(comps[3])
            hour, minute = int(comps[4]), int(comps[5])
            second = float(comps[6])
            flag = int(comps[7])
            nsat = int(comps[8])
        except (ValueError, IndexError):
            self._anom(lineno, "bad_epoch_line", "error",
                       "历元行字段无法解析: %r" % line[:60])
            # 仍建一个占位历元，后续卫星行不会被误拼
            ep = Epoch(len(self.epochs), lineno, line, 0, 0, 0, 0, 0, 0.0,
                       self.header.time_system or "", -1, "无法解析的历元行",
                       None, _format_epoch_time(0, 1, 1, 0, 0, 0),
                       obs_types_snapshot=self._snapshot_types())
            return ep, i + 1

        clock_offset = None
        if len(comps) > 9:
            try:
                clock_offset = float(comps[9])
            except ValueError:
                self._anom(lineno, "bad_clock_offset", "warning",
                           "历元钟偏字段无法解析: %r" % comps[9])

        tsys = self.header.time_system or ""
        ep = Epoch(
            index=len(self.epochs),
            line=lineno,
            raw_line=line,
            year=year, month=month, day=day, hour=hour, minute=minute,
            second=second,
            time_system=tsys,
            epoch_flag=flag,
            flag_meaning=EPOCH_FLAGS.get(flag, f"未知历元标志({flag})"),
            clock_offset=clock_offset,
            epoch_time=_format_epoch_time(year, month, day, hour, minute, second),
            obs_types_snapshot=self._snapshot_types(),
        )
        if flag not in EPOCH_FLAGS:
            self._anom(lineno, "unknown_epoch_flag", "warning",
                       f"历元标志 {flag} 不在 RINEX 3.05 定义内",
                       epoch=ep.epoch_time)

        # 读取该历元声明的卫星记录行
        j = i + 1
        seen = 0
        while seen < nsat:
            if j >= n:
                # 真正的文件截断：卫星行没给全，且后面没有任何行
                ep.truncated = True
                self._anom(lineno, "file_truncated", "error",
                           f"历元 {ep.epoch_time} 声明 {nsat} 颗卫星，仅读到 {seen} 条记录后文件结束"
                           "（判定为文件截断，不用后续内容补齐）",
                           epoch=ep.epoch_time)
                return ep, j
            sat_line = self.lines[j]
            if not sat_line.strip():
                # 卫星记录中间出现空行：RINEX 不允许，判为截断迹象
                ep.truncated = True
                self._anom(j + 1, "file_truncated", "error",
                           f"历元 {ep.epoch_time} 第 {seen + 1}/{nsat} 条卫星记录处遇到空行/文件结束"
                           "（判定为截断）",
                           epoch=ep.epoch_time)
                return ep, j
            if EPOCH_RE.match(sat_line):
                # 下一历元提前开始：当前历元卫星记录缺失，属截断，
                # 绝不把下一历元的行拼过来补齐
                ep.truncated = True
                self._anom(lineno, "epoch_truncated", "error",
                           f"历元 {ep.epoch_time} 声明 {nsat} 颗卫星，仅读到 {seen} 条即遇到下一历元"
                           "（判定为该历元截断，不拼补下一历元）",
                           epoch=ep.epoch_time)
                return ep, j
            # 既不是合法卫星行也不是历元行：结构异常。
            # 只报错并跳过本行，绝不当作续行与相邻行拼接，也不占用卫星名额。
            if not SATELLITE_RE.match(sat_line[0:3].strip()):
                self._anom(j + 1, "unexpected_line", "error",
                           "数据体中出现无法识别的行（已跳过，未与相邻行拼接）: %r"
                           % sat_line[:40], epoch=ep.epoch_time)
                j += 1
                continue
            rec, j = self._parse_satellite(sat_line, j, ep)
            if rec is not None:
                ep.satellites.append(rec)
            seen += 1

        # 事件类历元的附加信息
        if flag in (1, 2, 3, 5, 6):
            ep.events.append(EPOCH_FLAGS.get(flag, "事件"))
        if flag == 1 and nsat == 0:
            ep.events.append("开机事件历元（无卫星观测记录）")
        if flag == 5 and nsat == 0:
            ep.events.append("外部事件历元（无卫星观测记录）")

        # flag=4：其后的行是头部更新块，直到遇到下一个历元行
        if flag == 4:
            j = self._parse_header_update(ep, j)

        return ep, j  # j 指向下一未消费行的 0 基下标（已跳过历元行与全部卫星行）

    def _parse_satellite(self, line: str, idx: int, ep: Epoch):
        """idx 为该行在 self.lines 中的 0 基下标；返回 (记录或 None, 下一行下标)。"""
        lineno = idx + 1
        sat_id = line[0:3].strip()
        m = SATELLITE_RE.match(sat_id)
        if not m:
            self._anom(lineno, "bad_satellite_id", "error",
                       f"卫星标识 {sat_id!r} 不符合 RINEX 3 格式（系统字母+两位编号），本行跳过",
                       epoch=ep.epoch_time)
            return None, idx + 1
        system = m.group(1)
        if system not in self._cur_obs_types:
            self._anom(lineno, "unknown_system", "error",
                       f"卫星 {sat_id} 所属系统 {system} 没有头部观测类型定义，无法解释字段",
                       epoch=ep.epoch_time, satellite=sat_id)
            types: list[str] = []
        else:
            types = self._cur_obs_types[system]

        rec = SatelliteRecord(satellite=sat_id, system=system,
                              line=lineno, raw_line=line)

        # RINEX 3：每个观测字段固定 16 列，从第 4 列开始；一条卫星记录就是一整行，
        # 不按 80 字符截断、不与下一行拼接。
        n_fields = max(1, (len(line) - 3 + 15) // 16)
        chunks = [line[3 + k * 16: 3 + (k + 1) * 16] for k in range(n_fields)]
        # 行尾对齐产生的全空填充块不算字段；字段中间的全空块保留（合法缺测）
        while chunks and chunks[-1] == " " * 16:
            chunks.pop()
        while chunks and chunks[-1] == "":
            chunks.pop()

        if len(chunks) > len(types):
            extra = len(chunks) - len(types)
            self._anom(lineno, "extra_fields", "warning",
                       f"卫星 {sat_id} 行有 {len(chunks)} 个字段，超出系统 {system} 当前定义的 "
                       f"{len(types)} 个观测类型，多余 {extra} 个字段忽略（不跨行拼补）",
                       epoch=ep.epoch_time, satellite=sat_id)

        for type_idx, obs_type in enumerate(types):
            if type_idx >= len(chunks):
                # 合法的尾部省略：按缺测补齐，标记原因，绝不取下一行内容
                rec.observations.append(ObsValue(
                    obs_type=obs_type, value=None, missing=True,
                    missing_reason="trailing_omission", field_index=type_idx,
                    raw_field="", source_line=lineno))
                continue
            rec.observations.append(
                self._parse_obs_field(chunks[type_idx], obs_type, type_idx,
                                      lineno, ep, sat_id))

        return rec, idx + 1

    def _parse_obs_field(self, chunk: str, obs_type: str, idx: int,
                         lineno: int, ep: Epoch, sat_id: str) -> ObsValue:
        value_txt = chunk[0:14]
        lli_txt = chunk[14:15].strip()
        ssi_txt = chunk[15:16].strip()
        stripped = value_txt.strip()

        ob = ObsValue(obs_type=obs_type, value=None, field_index=idx,
                      raw_field=chunk, source_line=lineno)
        # LLI / SSI 独立保存，即使数值缺测也保留标记
        ob.lli = lli_txt or None
        ob.ssi = ssi_txt or None
        if lli_txt and not lli_txt.isdigit():
            self._anom(lineno, "bad_lli", "warning",
                       f"卫星 {sat_id} 观测 {obs_type} 的 LLI 标记 {lli_txt!r} 非数字",
                       epoch=ep.epoch_time, satellite=sat_id)
        if ssi_txt and not ssi_txt.isdigit():
            self._anom(lineno, "bad_ssi", "warning",
                       f"卫星 {sat_id} 观测 {obs_type} 的 SSI 标记 {ssi_txt!r} 非数字",
                       epoch=ep.epoch_time, satellite=sat_id)

        if stripped == "":
            ob.missing = True
            ob.missing_reason = "blank"
            return ob
        try:
            val = float(stripped)
        except ValueError:
            ob.missing = True
            ob.missing_reason = "unparseable"
            self._anom(lineno, "bad_obs_value", "warning",
                       f"卫星 {sat_id} 观测 {obs_type} 数值无法解析: {stripped!r}，按缺测处理",
                       epoch=ep.epoch_time, satellite=sat_id)
            return ob
        if val == 0.0:
            # RINEX 3.05 §5.6：全零或空字段表示缺测
            ob.missing = True
            ob.missing_reason = "zero_blank"
            return ob
        ob.value = val
        return ob

    def _parse_header_update(self, ep: Epoch, j: int) -> int:
        """解析 flag=4 之后、下一历元之前的头部续行；更新只对之后的记录生效。"""
        self._header_update_no += 1
        update = {"update_no": self._header_update_no, "changes": [], "lines": []}
        n = len(self.lines)
        while j < n:
            line = self.lines[j]
            lineno = j + 1
            if EPOCH_RE.match(line) or not line.strip():
                break
            label = line[60:80].strip() if len(line) >= 60 else ""
            update["lines"].append({"line": lineno, "text": line, "label": label})
            if label == "SYS / # / OBS TYPES":
                before = {k: list(v) for k, v in self._cur_obs_types.items()}
                last = self._parse_obs_types_header(j, line, lineno)
                after = {k: list(v) for k, v in self._cur_obs_types.items()}
                for sys_, types in after.items():
                    if before.get(sys_) != types:
                        update["changes"].append(
                            {"system": sys_, "obs_types": types,
                             "previous": before.get(sys_, [])})
                j = last + 1
                continue
            if label:
                update["changes"].append({"label": label, "text": line[0:60].strip()})
                self._apply_simple_header_line(label, line, lineno)
            else:
                self._anom(lineno, "bad_header_update", "warning",
                           "flag=4 头部更新块中出现无标签行，已忽略",
                           epoch=ep.epoch_time)
            j += 1
        ep.header_update = update
        ep.events.append(f"头部信息更新（对其后历元生效）：{len(update['changes'])} 项变化")
        self._anom(ep.line, "header_updated", "info",
                   f"历元 {ep.epoch_time} 声明头部更新，共 {len(update['changes'])} 项，"
                   "仅作用于之后的记录", epoch=ep.epoch_time)
        return j

    def _apply_simple_header_line(self, label: str, line: str, lineno: int):
        if label == "MARKER NAME":
            self.header.marker_name = line[0:60].strip() or self.header.marker_name
        elif label == "MARKER NUMBER":
            self.header.marker_number = line[0:60].strip() or self.header.marker_number
        elif label == "REC # / TYPE / VERS":
            self.header.receiver_number = line[0:20].strip() or self.header.receiver_number
            self.header.receiver_type = line[20:40].strip() or self.header.receiver_type
            self.header.receiver_version = line[40:60].strip() or self.header.receiver_version
        elif label == "ANT # / TYPE":
            self.header.antenna_number = line[0:20].strip() or self.header.antenna_number
            self.header.antenna_type = line[20:40].strip() or self.header.antenna_type
        elif label == "APPROX POSITION XYZ":
            vals = self._three_floats(line, lineno, label)
            if vals is not None:
                self.header.approx_position = vals
        elif label == "ANTENNA: DELTA H/E/N":
            vals = self._three_floats(line, lineno, label)
            if vals is not None:
                self.header.antenna_delta = vals
                self.header.antenna_height = vals[0]
        elif label == "TIME OF FIRST OBS":
            self._parse_first_obs(line, lineno)
        # 其余标签在更新块中保留原文，不影响数值解释

    # ------------------------------------------------------------------ #
    # 汇总
    # ------------------------------------------------------------------ #
    def _snapshot_types(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._cur_obs_types.items()}

    def _finalize_stats(self):
        total_obs = miss = lli_cnt = ssi_cnt = 0
        per_system: dict[str, dict] = {}
        for ep in self.epochs:
            for sat in ep.satellites:
                ps = per_system.setdefault(sat.system, {"satellites": set(), "observations": 0,
                                                        "missing": 0})
                ps["satellites"].add(sat.satellite)
                for ob in sat.observations:
                    total_obs += 1
                    ps["observations"] += 1
                    if ob.missing:
                        miss += 1
                        ps["missing"] += 1
                    if ob.lli is not None:
                        lli_cnt += 1
                    if ob.ssi is not None:
                        ssi_cnt += 1
        self._stats = {
            "epoch_count": len(self.epochs),
            "normal_epoch_count": sum(1 for e in self.epochs if e.epoch_flag == 0),
            "event_epoch_count": sum(1 for e in self.epochs if e.epoch_flag not in (0, 4)),
            "header_update_count": self._header_update_no,
            "satellite_record_count": sum(len(e.satellites) for e in self.epochs),
            "observation_field_count": total_obs,
            "missing_count": miss,
            "lli_count": lli_cnt,
            "ssi_count": ssi_cnt,
            "anomaly_error_count": sum(1 for a in self.anomalies if a.severity == "error"),
            "anomaly_warning_count": sum(1 for a in self.anomalies if a.severity == "warning"),
            "per_system": {k: {"satellites": sorted(v["satellites"]),
                               "satellite_count": len(v["satellites"]),
                               "observations": v["observations"],
                               "missing": v["missing"]}
                           for k, v in sorted(per_system.items())},
        }

    def _anom(self, line, code: str, severity: str, message: str,
              epoch: Optional[str] = None, satellite: Optional[str] = None):
        self.anomalies.append(Anomaly(line=line, code=code, severity=severity,
                                      message=message, epoch=epoch, satellite=satellite))


def parse_rinex_text(text: str, filename: str = "<memory>") -> ParseResult:
    return Rinex3ObsParser(text, filename).parse()
