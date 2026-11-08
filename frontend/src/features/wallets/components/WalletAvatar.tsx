import clsx from "clsx";

import { Icon } from "@/components/ui/Icon";
import type { Wallet } from "@/lib/api/types";

import { isEmoji, WALLET_ICON } from "../model";

/** Ícono circular de una billetera (emoji elegido o ícono por rol). */
export function WalletAvatar({ wallet, size = "md" }: { wallet: Wallet; size?: "sm" | "md" }) {
  const box = size === "sm" ? "h-9 w-9 text-[18px]" : "h-11 w-11 text-[22px]";
  return (
    <span className={clsx("flex shrink-0 items-center justify-center rounded-full bg-primary-fixed text-primary-container", box)}>
      {isEmoji(wallet.icon) ? wallet.icon : <Icon name={WALLET_ICON[wallet.role]} />}
    </span>
  );
}
