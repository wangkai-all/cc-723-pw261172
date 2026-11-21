# RINEX 3.05 观测数据接收站

上传 RINEX 3.05 合成观测文件（`*.*O`），在网页按**测站、历元、卫星、观测类型**
查看测量值、缺测标记、LLI/SSI 质量标记与事件，并可按系统和时间段导出。
**只整理 GNSS 原始观测，不计算任何定位结果。**

技术栈：Python 3.11 · FastAPI · React 18（Vite）。georinex 仅用于测试中的
交叉校验，事件与来源行由本项目解析器独立保留。

## 快速开始

```bash
# 1. 后端（项目根目录）
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# 2. 生成样例文件（确定性，无随机数据）
.venv/bin/python -I scripts/generate_samples.py

# 3. 前端构建（产物输出到 backend/static，由 FastAPI 托管）
cd frontend && npm install && npm run build && cd ..

# 4. 启动服务
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# 浏览器打开 http://127.0.0.1:8000
```

前端开发模式（热更新）：`cd frontend && npm run dev`，Vite 把 `/api` 代理到 8000。

## 测试

```bash
.venv/bin/python -m pytest backend/tests/ -q
```

共 32 项测试：解析器边界测试、FastAPI 接口集成测试、与 georinex 的逐数值交叉校验。

## 解析规则（对应 RINEX 3.05 第 5 章 / 附录 A）

| 规则 | 实现 |
| --- | --- |
| 观测类型列解释 | 按头部 `SYS / # / OBS TYPES` 各系统的类型列表解释三字符编码（类型+频段+通道），网页逐列给出含义 |
| 头部续行接齐 | 续行第 0 列必须为空；首行 13 槽、续行 13 槽按 4 列固定宽度合并，不与下一系统的定义行混淆 |
| 长行读取 | 卫星记录按**完整一行**读取，每字段固定 16 列（14 数值 + LLI + SSI）；**不套用 RINEX 2 的 80 字符物理续行拼接** |
| 按当前系统列数解释 | 每颗卫星按其系统当前生效的类型数解释；超长字段只告警忽略，绝不跨行拼补 |
| 合法尾部省略 | 卫星行尾部字段为空属合法省略，按缺测补齐并标记 `trailing_omission`，**不判截断、不取下一颗卫星/下一历元的行补齐** |
| 真正截断 | 声明的卫星记录数不足即遇 EOF/空行/下一历元，判 `file_truncated`/`epoch_truncated` 错误并逐项报告行号 |
| 历元标志 | 0 正常；1/2/3/5/6 事件；4 头部信息变化 |
| 头部更新（flag=4） | 更新块解析后只作用于**之后**的历元；每个历元保存当时生效的观测定义快照 |
| LLI / SSI | 丢锁标记与信号强度标记独立存储，不并入测量值；**缺测字段上的标记也保留**（georinex 会丢弃，本项目不会） |
| 缺测值 | 全空字段（`blank`）、0.0 空值（`zero_blank`）、尾部省略、不可解析值分别标记原因，数值为 `null` |
| 时间系统 | 支持 GPS/GLO/GAL/QZS/BDT/IRN/GST；不支持的系统只报错误、时间分量原样保留，**不擅自换算** |
| 来源保留 | 每行原文与 1 基行号保留；任意数值可回溯原行（含 ±2 行上下文） |

## 样例覆盖的场景

`backend/samples/SAMPLE_MIXED_305.06O`（脚本生成）包含：

1. 四系统不同列数：G=16、R=8、E=13、C=6
2. 259 字符的卫星观测长行（远超 80 字符阈值）
3. G 系统观测类型的头部续行
4. E01（10/13 字段）与更新后 G03（6/8 字段）的合法尾部省略
5. flag=4 头部更新（G 由 16 类型变 8，仅影响之后历元）
6. flag=1 开机事件、flag=5 外部事件
7. LLI 丢锁、SSI 信号强度、全空缺测（保留标记）、0.0 空值
8. 末尾真正截断的历元（声明 3 星仅给 2 行即 EOF）

`SAMPLE_BAD_TIMESYS_305.06O`：声明不支持的时间系统 `FOO`，验证只报告不换算。

## 目录结构

```
backend/
  app/parser.py     RINEX 3.05 解析器（无第三方依赖，纯标准库）
  app/service.py    内存存储、查询、CSV/JSON 导出
  app/main.py       FastAPI 路由 + 静态页托管
  tests/            32 项 pytest 测试
  samples/          生成的样例文件
frontend/           React + Vite 前端
scripts/generate_samples.py  样例生成器
```

## 主要 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/files` | 上传并解析，返回头部、统计、异常、历元概要 |
| GET | `/api/files/{id}/summary` | 测站信息、观测定义、异常列表 |
| GET | `/api/files/{id}/epochs?system=&start=&end=` | 按系统/时间段过滤历元 |
| GET | `/api/files/{id}/epochs/{index}` | 历元详情（全部卫星与字段） |
| GET | `/api/files/{id}/satellites/{sat}` | 单卫星跨历元序列 |
| GET | `/api/files/{id}/source-line/{line_no}` | 原行与上下文（数值溯源） |
| GET | `/api/files/{id}/report` | 接收报告（逐项异常、行号） |
| GET | `/api/files/{id}/export?format=csv|json&system=&start=&end=` | 按系统/时间段导出 |
