import { Suspense } from "react";

import { AmountScreen } from "@/features/yapeo/AmountScreen";

export default function YapearPage() {
  return (
    <Suspense>
      <AmountScreen />
    </Suspense>
  );
}
