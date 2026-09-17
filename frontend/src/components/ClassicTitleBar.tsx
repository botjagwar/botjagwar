interface ClassicTitleBarProps {
  title: string;
}

export function ClassicTitleBar({ title }: ClassicTitleBarProps) {
  return (
    <div className="classic-titlebar" aria-hidden="true">
      <span className="classic-titlebar__icon"><i /><i /></span>
      <strong>{title}</strong>
      <span className="classic-titlebar__controls"><i /><i /><i /></span>
    </div>
  );
}
