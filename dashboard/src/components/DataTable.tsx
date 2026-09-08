import { useState } from 'react'
import styles from './DataTable.module.css'

export interface DataColumn<T> {
  key: string
  header: string
  render: (row: T) => React.ReactNode
  /** Accessible column description for screen readers. */
  ariaLabel?: string
}

interface DataTableProps<T> {
  columns: Array<DataColumn<T>>
  rows: T[]
  rowKey: (row: T) => string
  /** §25: pagination over virtualization in MVP. */
  pageSize?: number
  caption?: string
  emptyMessage?: string
}

/** Generic tabular data display with pagination (§25). */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  pageSize = 50,
  caption,
  emptyMessage = 'No rows to display.',
}: DataTableProps<T>) {
  const [page, setPage] = useState(0)
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize))
  const visible = rows.slice(page * pageSize, (page + 1) * pageSize)

  if (rows.length === 0) {
    return <p className={styles.empty}>{emptyMessage}</p>
  }

  return (
    <div>
      <table className={`data-table ${styles.table}`}>
        {caption && <caption className={styles.caption}>{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" aria-label={column.ariaLabel}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {pageCount > 1 && (
        <div className={styles.pager}>
          <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <span>
            Page {page + 1} of {pageCount} ({rows.length} rows)
          </span>
          <button type="button" disabled={page >= pageCount - 1} onClick={() => setPage(page + 1)}>
            Next
          </button>
        </div>
      )}
    </div>
  )
}
