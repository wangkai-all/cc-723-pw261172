import { explainObsType, systemName } from '../obsDictionary.js'

export default function Overview({ data }) {
  const { header, stats, systems, obs_types: obsTypes } = data
  return (
    <div>
      <div className="panel">
        <h2>测站信息</h2>
        <div className="kv">
          <span className="k">文件名</span>
          <span>{data.filename}</span>
          <span className="k">RINEX 版本 / 类型</span>
          <span>
            {header.version} / {header.file_type}（{header.satellite_system} 混合文件）
          </span>
          <span className="k">测站标记</span>
          <span>
            {header.marker_name ?? '—'}
            {header.marker_number ? `（编号 ${header.marker_number}）` : ''}
          </span>
          <span className="k">接收机</span>
          <span>
            {[header.receiver_number, header.receiver_type, header.receiver_version]
              .filter(Boolean)
              .join(' / ') || '—'}
          </span>
          <span className="k">天线</span>
          <span>
            {[header.antenna_number, header.antenna_type].filter(Boolean).join(' / ') || '—'}
          </span>
          <span className="k">近似坐标 (X/Y/Z)</span>
          <span className="value">
            {header.approx_position
              ? header.approx_position.map((v) => v.toFixed(4)).join('  ')
              : '—'}
          </span>
          <span className="k">首个观测时间</span>
          <span>
            {header.first_observation_time
              ? header.first_observation_time.slice(0, 6).join(' ') +
                '  时间系统：' +
                (header.time_system || '未声明')
              : '—'}
          </span>
          <span className="k">头部结束行</span>
          <span>第 {header.end_of_header_line} 行</span>
        </div>
      </div>

      <div className="panel">
        <h2>接收统计</h2>
        <div className="grid cols-4">
          <Stat num={stats.epoch_count} label="历元总数" />
          <Stat num={stats.normal_epoch_count} label="正常观测历元" />
          <Stat num={stats.event_epoch_count} label="事件历元" />
          <Stat num={stats.header_update_count} label="头部更新次数" />
          <Stat num={stats.satellite_record_count} label="卫星观测记录" />
          <Stat num={stats.observation_field_count} label="观测字段总数" />
          <Stat num={stats.missing_count} label="缺测字段" />
          <Stat
            num={`${stats.lli_count}/${stats.ssi_count}`}
            label="LLI 标记 / SSI 标记"
          />
        </div>
      </div>

      <div className="panel">
        <h2>各系统观测类型定义（列解释）</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          三字符编码 = 观测类型 + 频段 + 通道码；数据体严格按此顺序与列数解释字段。
        </p>
        {systems.map((sys) => (
          <div key={sys} style={{ marginBottom: 14 }}>
            <h3>
              <span className="badge sys">{sys}</span> {systemName(sys)} ·{' '}
              {obsTypes[sys].length} 列
              {header.obs_types_lines?.[sys] && (
                <span className="muted">
                  {' '}
                  （头部第 {header.obs_types_lines[sys].join('、')} 行
                  {header.obs_types_lines[sys].length > 1 ? '，含续行' : ''}）
                </span>
              )}
            </h3>
            <div className="pill-row">
              {obsTypes[sys].map((t, i) => {
                const ex = explainObsType(t, sys)
                return (
                  <span
                    key={t + i}
                    className="pill"
                    title={`第 ${i + 1} 列：${ex.meaning}`}
                  >
                    {i + 1}. {t}
                  </span>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>头部原始行</h2>
        <pre className="raw">
          {header.raw_lines.map((l) => `${String(l.line).padStart(4, ' ')} │ ${l.text}\n`)}
        </pre>
      </div>
    </div>
  )
}

function Stat({ num, label }) {
  return (
    <div className="stat">
      <div className="num">{num}</div>
      <div className="label">{label}</div>
    </div>
  )
}
