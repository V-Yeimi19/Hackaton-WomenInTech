"use client";

import { useCallback, useEffect, useState } from "react";

/** Estado persistido en sessionStorage/localStorage, tolerante a modo privado o SSR. */
export function useStoredState<T>(key: string, initial: T, storage: "session" | "local" = "session") {
  const [value, setValue] = useState<T>(initial);

  useEffect(() => {
    try {
      const store = storage === "session" ? window.sessionStorage : window.localStorage;
      const raw = store.getItem(key);
      if (raw !== null) setValue(JSON.parse(raw) as T);
    } catch {
      /* almacenamiento no disponible: se usa el valor inicial */
    }
  }, [key, storage]);

  const update = useCallback(
    (next: T | ((previous: T) => T)) => {
      setValue((previous) => {
        const resolved = typeof next === "function" ? (next as (p: T) => T)(previous) : next;
        try {
          const store = storage === "session" ? window.sessionStorage : window.localStorage;
          store.setItem(key, JSON.stringify(resolved));
        } catch {
          /* sin persistencia */
        }
        return resolved;
      });
    },
    [key, storage],
  );

  return [value, update] as const;
}
