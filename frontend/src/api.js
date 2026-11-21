// 后端 API 封装。所有时间均为文件原始时间系统，前端不做任何时区换算。
const BASE = '/api'

async function request(path, options) {
  const resp = await fetch(BASE + path, options)
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      detail = (await resp.json()).detail || detail
    } catch {
      /* 忽略 JSON 解析失败 */
    }
    throw new Error(detail)
  }
  return resp.json()
}

export function uploadFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  return request('/files', { method: 'POST', body: fd })
}

export const getSummary = (id) => request(`/files/${id}/summary`)
export const getEpochs = (id, params = {}) => {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v != null),
  ).toString()
  return request(`/files/${id}/epochs${q ? '?' + q : ''}`)
}
export const getEpoch = (id, index) =>
  request(`/files/${id}/epochs/${index}`)
export const getSatelliteHistory = (id, sat, obsType) => {
  const q = obsType ? `?obs_type=${encodeURIComponent(obsType)}` : ''
  return request(`/files/${id}/satellites/${encodeURIComponent(sat)}${q}`)
}
export const getSourceLine = (id, lineNo) =>
  request(`/files/${id}/source-line/${lineNo}`)
export const getReport = (id) => request(`/files/${id}/report`)

export function exportUrl(id, { format, system, start, end }) {
  const q = new URLSearchParams(
    Object.entries({ format, system, start, end }).filter(
      ([, v]) => v !== '' && v != null,
    ),
  ).toString()
  return `${BASE}/files/${id}/export?${q}`
}
