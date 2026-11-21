import { useState } from 'react'
import { exportUrl } from '../api.js'

export default function ExportView({ data }) {
  const [fmt, setFmt] = useState('csv')
  const [system, setSystem] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')

  const url = exportUrl(data.file_id, {
    format: fmt,
    system,
    start,
    end,
  })

  return (
    <div className="panel">
      <h2>按系统与时间段导出</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        导出仅含 GNSS 原始观测：数值、缺测标记及原因、LLI/SSI 质量标记、来源行号；
        时间戳保留文件原始时间系统，未做任何换算。不包含定位结果。
      </p>
      <div className="filters">
        <label>
          格式
          <select value={fmt} onChange={(e) => setFmt(e.target.value)}>
            <option value="csv">CSV（Excel 可打开，UTF-8 BOM）</option>
            <option value="json">JSON（结构化，含历元与头部快照）</option>
          </select>
        </label>
        <label>
          卫星系统
          <select value={system} onChange={(e) => setSystem(e.target.value)}>
            <option value="">全部系统</option>
            {data.systems.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          起始时间（含）
          <input
            type="datetime-local"
            step="1"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          结束时间（含）
          <input
            type="datetime-local"
            step="1"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <a className="btn" href={url}>
          下载导出文件
        </a>
      </div>

      <h3>CSV 列说明</h3>
      <div className="pill-row">
        {[
          'epoch_time 历元时间',
          'time_system 原始时间系统',
          'epoch_flag 历元标志',
          'system/satellite 系统与卫星',
          'obs_type 观测类型',
          'value 测量数值（缺测为空）',
          'missing 缺测标记 1/0',
          'missing_reason 缺测原因',
          'lli 丢锁标记',
          'ssi 信号强度',
          'source_line 原行号',
        ].map((c) => (
          <span key={c} className="pill">
            {c}
          </span>
        ))}
      </div>
    </div>
  )
}
