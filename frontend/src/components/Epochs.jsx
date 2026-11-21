import { useEffect, useState } from 'react'
import { getEpoch, getEpochs } from '../api.js'
import { explainObsType } from '../obsDictionary.js'
import { ObsCell, SourceModal } from './SourceModal.jsx'

export default function Epochs({ data }) {
  const [filters, setFilters] = useState({ system: '', start: '', end: '' })
  const [list, setList] = useState(null)
  const [selected, setSelected] = useState(0)
  const [detail, setDetail] = useState(null)
  const [err, setErr] = useState('')

  async function reloadList(f) {
    try {
      const r = await getEpochs(data.file_id, f)
      setList(r.epochs)
      if (r.epochs.length) {
        setSelected(r.epochs[0].index)
      } else {
        setDetail(null)
      }
    } catch (e) {
      setErr(e.message)
    }
  }

  useEffect(() => {
    reloadList(filters)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selected == null) return
    getEpoch(data.file_id, selected).then(setDetail).catch((e) => setErr(e.message))
  }, [selected, data.file_id])

  return (
    <div>
      <div className="panel">
        <h2>历元筛选</h2>
        <div className="filters">
          <label>
            卫星系统
            <select
              value={filters.system}
              onChange={(e) =>
                setFilters((f) => ({ ...f, system: e.target.value }))
              }
            >
              <option value="">全部</option>
              {data.systems.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label>
            起始时间（含，原始时间系统）
            <input
              type="datetime-local"
              step="1"
              value={filters.start}
              onChange={(e) =>
                setFilters((f) => ({ ...f, start: toIso(e.target.value) }))
              }
            />
          </label>
          <label>
            结束时间（含）
            <input
              type="datetime-local"
              step="1"
              value={filters.end}
              onChange={(e) =>
                setFilters((f) => ({ ...f, end: toIso(e.target.value) }))
              }
            />
          </label>
          <button className="btn" onClick={() => reloadList(filters)}>
            应用筛选
          </button>
        </div>
        {err && <p className="error-text">{err}</p>}
      </div>

      <div className="panel">
        <h2>历元列表（{list?.length ?? 0}）</h2>
        <div className="table-wrap" style={{ maxHeight: 260 }}>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>行号</th>
                <th>历元时间（{data.header.time_system || '未声明'}）</th>
                <th>标志</th>
                <th>卫星数</th>
                <th>事件/状态</th>
              </tr>
            </thead>
            <tbody>
              {list?.map((e) => (
                <tr
                  key={e.index}
                  className={'clickable' + (e.index === selected ? ' active' : '')}
                  onClick={() => setSelected(e.index)}
                  style={
                    e.index === selected ? { background: 'var(--accent-soft)' } : {}
                  }
                >
                  <td className="num">{e.index}</td>
                  <td className="num">{e.line}</td>
                  <td className="value">{e.epoch_time}</td>
                  <td>
                    <span className={'flag-dot f' + e.epoch_flag} />
                    {e.epoch_flag} · {e.flag_meaning}
                  </td>
                  <td className="num">{e.satellite_count}</td>
                  <td>
                    {e.truncated && <span className="badge error">截断</span>}{' '}
                    {e.has_header_update && (
                      <span className="badge info">头部更新</span>
                    )}{' '}
                    {e.events.join('，')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {detail && <EpochDetail fileId={data.file_id} detail={detail} />}
    </div>
  )
}

function EpochDetail({ fileId, detail }) {
  return (
    <div className="panel">
      <h2>
        历元 {detail.index} · {detail.epoch_time}{' '}
        <span className="muted">
          （时间系统 {detail.time_system}，钟偏{' '}
          {detail.clock_offset == null ? '无' : detail.clock_offset}）
        </span>
      </h2>

      {detail.header_update && (
        <div style={{ marginBottom: 12 }}>
          <span className="badge info">flag=4 头部更新（仅对之后历元生效）</span>
          {detail.header_update.changes.map((c, i) => (
            <div key={i} className="muted" style={{ marginTop: 6 }}>
              {c.system ? (
                <>
                  系统 {c.system} 观测类型：{c.previous?.join(' ') || '无'} →{' '}
                  {c.obs_types.join(' ')}
                </>
              ) : (
                <>
                  {c.label}：{c.text}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <p className="muted" style={{ marginTop: 0 }}>
        本历元生效的观测定义：
        {Object.entries(detail.obs_types_snapshot).map(([sys, types]) => (
          <span key={sys} className="pill" style={{ marginRight: 6 }}>
            {sys}: {types.length} 列
          </span>
        ))}
        ；点击任意数值/缺测单元格可查看原行与质量标记。
      </p>

      {detail.satellites.map((sat) => (
        <SatelliteTable key={sat.satellite} fileId={fileId} sat={sat} />
      ))}

      {detail.satellites.length === 0 && (
        <p className="muted">该历元无卫星观测记录（事件历元）。</p>
      )}
    </div>
  )
}

function SatelliteTable({ fileId, sat }) {
  const [inspect, setInspect] = useState(null) // { obs, def }
  return (
    <div style={{ marginBottom: 18 }}>
      <h3>
        <span className="badge sys">{sat.satellite}</span> 原始行第 {sat.line} 行 ·{' '}
        {sat.obs_count} 字段 · 缺测 {sat.missing_count} · LLI {sat.lli_count} · SSI{' '}
        {sat.ssi_count}
      </h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>观测类型</th>
              <th>列含义</th>
              <th className="num">值 / 缺测</th>
              <th>LLI</th>
              <th>SSI</th>
              <th>来源行</th>
            </tr>
          </thead>
          <tbody>
            {sat.observations.map((o) => {
              const ex = explainObsType(o.obs_type, sat.system)
              return (
                <tr key={o.field_index}>
                  <td className="num">{o.field_index + 1}</td>
                  <td className="value">{o.obs_type}</td>
                  <td className="muted" title={ex.meaning}>
                    {ex.kindMeaning} · {ex.bandMeaning}
                  </td>
                  <ObsCell obs={o} onInspect={(ob) => setInspect({ obs: ob, def: ex })} />
                  <td className="lli" title={o.lli_meaning?.join('；')}>
                    {o.lli || ''}
                  </td>
                  <td className="ssi" title={o.ssi_meaning}>
                    {o.ssi || ''}
                  </td>
                  <td className="num">{o.source_line}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {inspect && (
        <SourceModal
          fileId={fileId}
          lineNo={inspect.obs.source_line}
          obs={inspect.obs}
          obsTypeDef={inspect.def}
          onClose={() => setInspect(null)}
        />
      )}
    </div>
  )
}

// datetime-local 的 "YYYY-MM-DDTHH:mm:ss" 与后端 ISO 形式一致，直接透传
function toIso(v) {
  return v || ''
}
