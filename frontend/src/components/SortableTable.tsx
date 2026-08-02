import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

export interface Column<T> {
  key: keyof T
  label: string
  align?: 'left' | 'right'
  format?: (value: T[keyof T], row: T) => ReactNode
}

interface Props<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  renderActions?: (row: T) => ReactNode
}

type SortDir = 'asc' | 'desc'

export function SortableTable<T>({ columns, rows, rowKey, renderActions }: Props<T>) {
  const [sortKey, setSortKey] = useState<keyof T | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const topRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const syncingRef = useRef<'top' | 'bottom' | null>(null)
  const [scrollWidth, setScrollWidth] = useState(0)

  const sorted = useMemo(() => {
    if (!sortKey) return rows
    const copy = [...rows]
    copy.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (typeof av === 'number' && typeof bv === 'number') return av - bv
      return String(av).localeCompare(String(bv))
    })
    if (sortDir === 'desc') copy.reverse()
    return copy
  }, [rows, sortKey, sortDir])

  // mantém a barra de rolagem "fantasma" do topo com a mesma largura da tabela real,
  // e recalcula se a janela mudar de tamanho (colunas quebram linha, etc)
  useEffect(() => {
    function measure() {
      if (bottomRef.current) setScrollWidth(bottomRef.current.scrollWidth)
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [sorted, columns])

  function onTopScroll() {
    if (syncingRef.current === 'bottom') {
      syncingRef.current = null
      return
    }
    if (topRef.current && bottomRef.current) {
      syncingRef.current = 'top'
      bottomRef.current.scrollLeft = topRef.current.scrollLeft
    }
  }

  function onBottomScroll() {
    if (syncingRef.current === 'top') {
      syncingRef.current = null
      return
    }
    if (topRef.current && bottomRef.current) {
      syncingRef.current = 'bottom'
      topRef.current.scrollLeft = bottomRef.current.scrollLeft
    }
  }

  function onHeaderClick(key: keyof T) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  return (
    <div className="table-wrap">
      <div className="table-scroll-top" ref={topRef} onScroll={onTopScroll}>
        <div style={{ width: scrollWidth }} />
      </div>
      <div className="table-scroll" ref={bottomRef} onScroll={onBottomScroll}>
        <table className="table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={String(col.key)}
                  onClick={() => onHeaderClick(col.key)}
                  className={col.align === 'right' ? 'align-right' : undefined}
                >
                  {col.label}
                  {sortKey === col.key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                </th>
              ))}
              {renderActions && <th />}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((col) => (
                  <td key={String(col.key)} className={col.align === 'right' ? 'align-right' : undefined}>
                    {col.format ? col.format(row[col.key], row) : String(row[col.key])}
                  </td>
                ))}
                {renderActions && <td>{renderActions(row)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
