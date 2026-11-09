import { backend } from "@/lib/api/http";
import { useQuery } from "@tanstack/react-query";

export type DeclarationState = { id: string; version: number; status: string; actions: ("confirm" | "edit" | "cancel")[] };
export type DeclarationAction = { id: string; version: number; action: "confirm" | "edit" | "cancel" };
export type ChatTurn = { role: "user" | "assistant"; content: string; declaration?: DeclarationState | null };

export type BusinessProfile = { wallet_id: string; answers: string[]; version: number };
export type Exchange = { id: string; request_id: string; message: string; reply: string; created_at: string; declaration?: DeclarationState | null };
export type ChatPage = { items: Exchange[]; next_cursor: string | null };

export const getProfile = (walletId: string) => backend<BusinessProfile>(`agent/profile?wallet_id=${walletId}`);
export const saveProfile = (walletId: string, answers: string[], version: number) =>
  backend<BusinessProfile>("agent/profile", {
    method: "PATCH", body: { wallet_id: walletId, answers, expected_version: version },
  });
export const getChat = (walletId: string, cursor?: string) =>
  backend<ChatPage>(`agent/chat?wallet_id=${walletId}${cursor ? `&cursor=${cursor}` : ""}`);
export const sendChat = (walletId: string, message: string, requestId: string, action?: DeclarationAction) =>
  backend<Exchange>("agent/chat", {
    method: "POST", body: { wallet_id: walletId, message, request_id: requestId, declaration_action: action },
  });

export const chatTurns = (items: Exchange[]) => items.flatMap((item) => [
  { role: "user" as const, content: item.message },
  { role: "assistant" as const, content: item.reply, declaration: item.declaration },
]);

type DeclarationMemory = {
  pending: { reply: string; declaration: DeclarationState } | null;
  latest_confirmed: { id: string; confirmed_at: string; entries: { wallet_name: string; amount: string; medium: string; direction: string; description: string; day: string }[] } | null;
};
export function useDeclarationMemory(walletId: string) {
  return useQuery({ queryKey: ["declarations", walletId], queryFn: () => backend<DeclarationMemory>(`agent/declarations?wallet_id=${walletId}`), refetchInterval: 5000, refetchOnWindowFocus: "always" });
}
