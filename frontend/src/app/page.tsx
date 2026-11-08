import { Suspense } from "react";

import { HomeScreen } from "@/features/home/HomeScreen";

export default function HomePage() {
  return (
    <Suspense>
      <HomeScreen />
    </Suspense>
  );
}
