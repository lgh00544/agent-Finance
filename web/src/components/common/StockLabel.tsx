/** 股票标识（代码+名称；名称缺失或等于代码 → 「名称待补」，禁止只显示纯代码） */
export function StockLabel({ code, name }: { code: string; name?: string | null }) {
  const c = String(code ?? '').trim()
  const n = String(name ?? '').trim()
  const hasName = !!n && n !== c
  return (
    <span className="stock-label">
      <span className="code">{c}</span> {hasName ? n : <span className="missing">名称待补</span>}
    </span>
  )
}
