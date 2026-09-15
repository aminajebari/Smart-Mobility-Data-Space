import type { ReactNode } from 'react'

type Props = { title: string; eyebrow?: string; action?: ReactNode; children: ReactNode; className?: string }

export function Section({ title, eyebrow, action, children, className = '' }: Props) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel__header">
        <div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>
        {action}
      </div>
      {children}
    </section>
  )
}
