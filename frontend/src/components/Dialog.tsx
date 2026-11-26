import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
export function Dialog({
  title,
  children,
  close,
  wide = false,
  error = "",
  busy = false,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
  error?: string;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={"dialog " + (wide ? "wide" : "")}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) close();
      }}
      onClick={(e) => {
        if (!busy && e.target === e.currentTarget) close();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="关闭"
          onClick={close}
          disabled={busy}
        >
          <X size={20} />
        </button>
      </header>
      <div className="dialog-body">
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {children}
      </div>
    </dialog>
  );
}
