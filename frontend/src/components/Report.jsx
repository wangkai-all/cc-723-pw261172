export default function Report({ data }) {
  const { anomalies, stats, truncated } = data
  const sev = (s) =>
    ({ error: '错误', warning: '警告', info: '信息' }[s] || s)

  return (
    <div className="panel">
      <h2>
        接收报告
        {truncated ? (
          <span className="badge error" style={{ marginLeft: 10 }}>
            检测到文件截断
          </span>
        ) : (
          <span className="badge ok" style={{ marginLeft: 10 }}>
            结构完整
          </span>
        )}
      </h2>

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <div className="stat">
          <div className="num error-text">{stats.anomaly_error_count}</div>
          <div className="label">错误（影响完整性）</div>
        </div>
        <div className="stat">
          <div className="num" style={{ color: 'var(--warn)' }}>
            {stats.anomaly_warning_count}
          </div>
          <div className="label">警告（已按规则处理）</div>
        </div>
        <div className="stat">
          <div className="num" style={{ color: 'var(--info)' }}>
            {anomalies.filter((a) => a.severity === 'info').length}
          </div>
          <div className="label">信息（正常事件）</div>
        </div>
      </div>

      <p className="muted">
        逐项列出异常位置（行号、历元、卫星）。截断不会用相邻行拼补；
        合法尾部省略与真正截断已区分。
      </p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>行号</th>
              <th>级别</th>
              <th>代码</th>
              <th>历元</th>
              <th>卫星</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            {anomalies.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  无任何异常
                </td>
              </tr>
            )}
            {anomalies.map((a, i) => (
              <tr key={i}>
                <td className="num">{a.line ?? '—'}</td>
                <td>
                  <span className={'badge ' + a.severity}>{sev(a.severity)}</span>
                </td>
                <td className="value">{a.code}</td>
                <td className="value">{a.epoch || '—'}</td>
                <td className="value">{a.satellite || '—'}</td>
                <td>{a.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
