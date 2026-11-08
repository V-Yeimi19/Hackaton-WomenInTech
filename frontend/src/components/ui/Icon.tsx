import clsx from "clsx";

type IconProps = { name: string; filled?: boolean; className?: string; size?: number };

/** Ícono de Material Symbols (decorativo: el texto accesible va en el botón). */
export function Icon({ name, filled = false, className, size }: IconProps) {
  return (
    <span aria-hidden="true" className={clsx("material-symbols-outlined", filled && "filled", className)}
      style={size === undefined ? undefined : { fontSize: size, width: size, height: size, lineHeight: 1 }}>
      {name}
    </span>
  );
}
