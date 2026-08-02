import { useMemo, useState, type ReactNode } from 'react'

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

  function onHeaderClick(key: keyof T) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  return (
    <div className="table-scroll">
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
  )
}
