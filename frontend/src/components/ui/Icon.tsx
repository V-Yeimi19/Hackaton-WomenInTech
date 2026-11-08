import clsx from "clsx";

type IconProps = { name: string; filled?: boolean; className?: string };

/** Ícono de Material Symbols (decorativo: el texto accesible va en el botón). */
export function Icon({ name, filled = false, className }: IconProps) {
  return (
    <span aria-hidden="true" className={clsx("material-symbols-outlined", filled && "filled", className)}>
      {name}
    </span>
  );
}
