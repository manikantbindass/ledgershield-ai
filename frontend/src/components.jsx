import { useState } from 'react'
import { number, label } from './lib/utils'

const paths = {
  overview: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  network: 'M12 3v6M5 17l5-5m9 5-5-5M9 3h6v5H9zM2 17h6v5H2zM16 17h6v5h-6z',
  blockchain: 'm12 2 9 5v10l-9 5-9-5V7l9-5Zm0 10v10M3 7l9 5 9-5',
  security: 'm12 2 9 4v6c0 5-5 8-9 10-4-2-9-5-9-10V6l9-4Zm-4 10 3 3 5-6',
  trust: 'M4 20h16M6 16v-5m6 5V6m6 10V2',
  healing: 'M20 8a8 8 0 1 0 1 8M20 2v6h-6m-5 4h6m-3-3v6',
  rl: 'M8 4H5v5H2v6h3v5h5v2h4v-2h5v-5h3V9h-3V4h-5V2h-4v2H8Zm0 5h8v6H8z',
  simulation: 'm8 3 13 9-13 9V3ZM3 3v18',
  reports: 'M5 2h10l4 4v16H5V2Zm10 0v5h4M8 17v-4m4 4V9m4 8v-6',
  settings:
    'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm0-6v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  refresh: 'M20 8a8 8 0 1 0 1 8M20 2v6h-6',
  sun: 'M12 3v2m0 14v2M3 12h2m14 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8',
  menu: 'M3 6h18M3 12h18M3 18h18',
  check: 'm5 12 4 4L19 6',
}
export function Icon({ name, size = 19 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.overview} />
    </svg>
  )
}
export function Badge({ children, tone = '' }) {
  return <span className={`badge ${tone}`}>{children}</span>
}
export function Panel({ title, subtitle, action, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}
export function Empty({ title = 'No records yet', children }) {
  return (
    <div className="empty">
      <Icon name="reports" size={28} />
      <h3>{title}</h3>
      <p>{children || 'Records will appear here when the simulator produces them.'}</p>
    </div>
  )
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      Loading measured data…
    </div>
  )
}
export function Resource({ resource, children }) {
  if (resource.loading) return <Loading />
  return (
    <>
      {resource.error && (
        <div className="inline-error" role="alert">
          {resource.error.message}
          {resource.error.requestId && <code>Request {resource.error.requestId}</code>}
          <button onClick={resource.retry}>Retry</button>
        </div>
      )}
      {resource.data ? children(resource.data) : !resource.error && <Empty />}
    </>
  )
}
export function Pager({ resource }) {
  const total = resource.data?.total || 0
  return (
    <div className="pager">
      <span>
        {total
          ? `${resource.offset + 1}–${Math.min(resource.offset + resource.limit, total)} of ${total}`
          : '0 records'}
      </span>
      <div>
        <button
          disabled={resource.offset === 0}
          onClick={() => resource.setOffset(Math.max(0, resource.offset - resource.limit))}
        >
          Previous
        </button>
        <button
          disabled={resource.offset + resource.limit >= total}
          onClick={() => resource.setOffset(resource.offset + resource.limit)}
        >
          Next
        </button>
      </div>
    </div>
  )
}
export function Search({
  value,
  onChange,
  placeholder = 'Search records',
  label: text = 'Search records',
}) {
  return (
    <label className="search">
      <span>{text}</span>
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        maxLength={100}
      />
    </label>
  )
}
export function Table({ columns, rows, rowKey = 'id', empty }) {
  return rows.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.label} scope="col">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row[rowKey] ?? index}>
              {columns.map((c) => (
                <td key={c.label}>{c.render ? c.render(row) : row[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty>{empty}</Empty>
  )
}
export function Details({ title, onClose, children }) {
  return (
    <section className="details">
      <div className="panel-head">
        <h3>{title}</h3>
        <button aria-label="Close details" onClick={onClose}>
          Close
        </button>
      </div>
      {children}
    </section>
  )
}
export function KeyValues({ entries }) {
  return (
    <dl className="key-values">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{value ?? '—'}</dd>
        </div>
      ))}
    </dl>
  )
}
export function JSONDetails({ value, title = 'Evidence record' }) {
  return (
    <details className="json-details">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  )
}
export function Metric({ title, value, suffix, detail, icon = 'overview' }) {
  return (
    <article className="metric">
      <div className="metric-label">
        {title}
        <Icon name={icon} size={17} />
      </div>
      <div className="metric-value">
        {value}
        <small>{suffix}</small>
      </div>
      <p>{detail}</p>
    </article>
  )
}

export function LineChart({ rows, xKey = 'simulated_seconds', yKey, title, unit = '' }) {
  const [active, setActive] = useState(null)
  const values = rows.filter((row) => Number.isFinite(row[yKey]))
  if (!values.length)
    return (
      <Empty title="No samples recorded">
        Advance the simulator or load a recorded run to build this chart.
      </Empty>
    )
  const width = 720,
    height = 200,
    left = 48,
    bottom = 168
  const min = Math.min(0, ...values.map((r) => r[yKey])),
    max = Math.max(...values.map((r) => r[yKey]), min + 1)
  const point = (row, i) => [
    left + (values.length === 1 ? 0.5 : i / (values.length - 1)) * 648,
    bottom - ((row[yKey] - min) / (max - min)) * 140,
  ]
  const current = active === null ? values.length - 1 : Math.min(active, values.length - 1)
  return (
    <div className="chart">
      <div className="chart-caption">
        <span>{title}</span>
        <strong>
          {number(values[current][yKey], 3)} {unit}
          <small>
            {' '}
            · {label(xKey)} {values[current][xKey]}
          </small>
        </strong>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${title}. ${values.length} recorded samples. Use the data points or the data table for exact values.`}
      >
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line
              x1={left}
              y1={bottom - f * 140}
              x2="696"
              y2={bottom - f * 140}
              className="grid-line"
            />
            <text x="38" y={bottom - f * 140 + 4} textAnchor="end">
              {number(min + f * (max - min))}
            </text>
          </g>
        ))}
        <polyline
          points={values.map((row, i) => point(row, i).join(',')).join(' ')}
          fill="none"
          className="chart-line"
        />
        {values.map((row, i) => {
          const [cx, cy] = point(row, i)
          return (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={current === i ? 4 : 2}
              tabIndex="0"
              aria-label={`${label(xKey)} ${row[xKey]}: ${number(row[yKey], 3)} ${unit}`}
              onFocus={() => setActive(i)}
              onMouseEnter={() => setActive(i)}
              className="chart-point"
            />
          )
        })}
        <text x={left} y="193">
          {values[0][xKey]}
        </text>
        <text x="696" y="193" textAnchor="end">
          {values.at(-1)[xKey]} · {label(xKey)}
        </text>
      </svg>
      <label className="chart-scrubber">
        Inspect sample
        <input
          type="range"
          min="0"
          max={values.length - 1}
          value={current}
          onChange={(event) => setActive(Number(event.target.value))}
          aria-label={`Inspect ${title} sample`}
        />
      </label>
      <details className="chart-data">
        <summary>View chart data</summary>
        <Table
          columns={[
            { label: label(xKey), key: xKey },
            { label: title, render: (row) => `${number(row[yKey], 3)} ${unit}` },
          ]}
          rows={values.map((row, i) => ({ ...row, _sample: i }))}
          rowKey="_sample"
        />
      </details>
    </div>
  )
}

export function BarChart({ rows, valueKey = 'mean_reward', nameKey = 'policy', title }) {
  if (!rows.length) return <Empty title="No comparison available" />
  const max = Math.max(1, ...rows.map((row) => Math.abs(row[valueKey])))
  return (
    <div className="bar-chart" aria-label={title}>
      {rows.map((row, i) => (
        <div key={row.id || i}>
          <div>
            <span>{label(row[nameKey])}</span>
            <strong>{number(row[valueKey], 3)}</strong>
          </div>
          <progress
            aria-label={`${label(row[nameKey])}: ${number(row[valueKey], 3)}`}
            max={max}
            value={Math.abs(row[valueKey])}
          />
        </div>
      ))}
    </div>
  )
}
