/** Filas de carga con el mismo alto que un movimiento. */
export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Cargando movimientos">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex animate-pulse items-center justify-between gap-2 border-t border-surface-container-high px-4 py-3.5">
          <div className="min-w-0 flex-1">
            <div className="h-3.5 w-2/5 rounded-full bg-surface-container-high" />
            <div className="mt-2 h-3 w-3/5 rounded-full bg-surface-container" />
          </div>
          <div className="h-3.5 w-16 rounded-full bg-surface-container-high" />
        </div>
      ))}
    </div>
  );
}
