import { useState } from 'react'
import Upload from './components/Upload.jsx'
import Overview from './components/Overview.jsx'
import Epochs from './components/Epochs.jsx'
import Report from './components/Report.jsx'
import ExportView from './components/ExportView.jsx'

const TABS = [
  ['overview', '测站与头部'],
  ['epochs', '历元 / 卫星 / 观测值'],
  ['report', '接收报告'],
  ['export', '导出'],
]

export default function App() {
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('overview')

  return (
    <div className="app">
      <header className="app-header">
        <h1>RINEX 3.05 观测数据接收站</h1>
        <span className="sub">
          仅整理 GNSS 原始观测（值 · 缺测 · LLI/SSI · 事件 · 来源行），不做定位解算
        </span>
      </header>

      {!data ? (
        <Upload
          onUploaded={(d) => {
            setData(d)
            setTab('overview')
          }}
        />
      ) : (
        <>
          <div className="tabs">
            {TABS.map(([key, label]) => (
              <button
                key={key}
                className={tab === key ? 'active' : ''}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
            <button
              style={{ marginLeft: 'auto' }}
              onClick={() => setData(null)}
            >
              上传另一个文件
            </button>
          </div>

          <div style={{ marginBottom: 12 }}>
            <strong>{data.filename}</strong>{' '}
            <span className="muted">
              {data.systems.join(' / ')} · {data.stats.epoch_count} 个历元
            </span>{' '}
            {data.truncated && <span className="badge error">文件截断</span>}
            {data.stats.anomaly_warning_count > 0 && (
              <span className="badge warning" style={{ marginLeft: 6 }}>
                {data.stats.anomaly_warning_count} 项警告
              </span>
            )}
          </div>

          {tab === 'overview' && <Overview data={data} />}
          {tab === 'epochs' && <Epochs data={data} />}
          {tab === 'report' && <Report data={data} />}
          {tab === 'export' && <ExportView data={data} />}
        </>
      )}
    </div>
  )
}
