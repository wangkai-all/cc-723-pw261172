import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { getSourceLine } from '../api.js'

// 单个观测值单元格：只渲染 <td>，点击由父组件打开溯源弹窗
export function ObsCell({ obs, onInspect }) {
  return (
    <td
      className={'obs-cell ' + (obs.missing ? 'missing' : 'value')}
      title={
        obs.missing
          ? `缺测（${reasonText(obs.missing_reason)}），点击查看来源`
          : '点击查看原行与质量标记'
      }
      onClick={() => onInspect(obs)}
    >
      {obs.missing ? '—' : obs.value?.toFixed(3)}
    </td>
  )
}

export function reasonText(reason) {
  return (
    {
      blank: '字段全空',
      zero_blank: '0.0 空值（RINEX 规定视为缺测）',
      trailing_omission: '尾部合法省略',
      unparseable: '数值无法解析',
    }[reason] || reason
  )
}

// 溯源弹窗：原行、当时生效的观测定义、数值与质量标记
export function SourceModal({ fileId, lineNo, onClose, obs, obsTypeDef }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    getSourceLine(fileId, lineNo)
      .then(setData)
      .catch((e) => setErr(e.message))
  }, [fileId, lineNo])

  // Portal 到 body，避免弹窗节点嵌套在表格内
  return createPortal(
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>数值溯源 · 第 {lineNo} 行</h2>
          <button className="btn ghost" onClick={onClose}>
            关闭
          </button>
        </div>

        {obs && (
          <div className="kv" style={{ marginBottom: 14 }}>
            <span className="k">观测类型</span>
            <span>
              <span className="pill">{obs.obs_type}</span>{' '}
              {obsTypeDef?.meaning || ''}
            </span>
            <span className="k">生效定义中的列</span>
            <span>
              第 {obs.field_index + 1} 列（按该历元当时生效的系统观测类型列表）
            </span>
            <span className="k">测量数值</span>
            <span className="value">
              {obs.missing ? `缺测（${reasonText(obs.missing_reason)}）` : obs.value}
            </span>
            <span className="k">丢锁标记 LLI</span>
            <span className="lli">
              {obs.lli || '无'}
              {obs.lli_meaning?.length ? `（${obs.lli_meaning.join('；')}）` : ''}
            </span>
            <span className="k">信号强度 SSI</span>
            <span className="ssi">
              {obs.ssi || '无'}
              {obs.ssi_meaning ? `（${obs.ssi_meaning}）` : ''}
            </span>
            <span className="k">原始 16 列字段</span>
            <span className="pill">{obs.raw_field || '（尾部省略，无原文）'}</span>
          </div>
        )}

        <h3>原始记录行（上下文 ±2 行，未做任何拼接）</h3>
        {err && <p className="error-text">{err}</p>}
        {data && (
          <pre className="raw">
            {data.context.map((c) => (
              <span key={c.line} className={c.current ? 'cur' : 'ctx'}>
                {String(c.line).padStart(4, ' ')} │ {c.text || ' '}
                {'\n'}
              </span>
            ))}
          </pre>
        )}
      </div>
    </div>,
    document.body,
  )
}
