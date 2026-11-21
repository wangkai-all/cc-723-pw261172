import { useRef, useState } from 'react'
import { uploadFile } from '../api.js'

export default function Upload({ onUploaded }) {
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const inputRef = useRef()

  async function handleFile(file) {
    if (!file) return
    setBusy(true)
    setErr('')
    try {
      const data = await uploadFile(file)
      onUploaded(data)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div
        className={'upload-zone' + (drag ? ' drag' : '')}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDrag(false)
          handleFile(e.dataTransfer.files?.[0])
        }}
      >
        <div className="big">
          {busy ? '正在解析 RINEX 文件…' : '点击或拖拽上传 RINEX 3.05 观测文件'}
        </div>
        <div>支持 .06o / *.obs 等 RINEX 3 观测数据；仅整理原始观测，不做定位解算</div>
        <input
          ref={inputRef}
          type="file"
          style={{ display: 'none' }}
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>
      {err && <p className="error-text">上传/解析失败：{err}</p>}
    </div>
  )
}
