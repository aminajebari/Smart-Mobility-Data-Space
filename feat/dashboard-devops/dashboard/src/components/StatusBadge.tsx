type Props = { status: string }

export function StatusBadge({ status }: Props) {
  const key = status.toLowerCase()
  return <span className={`status status--${key}`}><i aria-hidden="true" />{status}</span>
}
