import { backend } from "@/lib/api/http";

export type BusinessProfile = { wallet_id: string; answers: string[]; version: number };
export type Exchange = { id: string; request_id: string; message: string; reply: string; created_at: string };
export type ChatPage = { items: Exchange[]; next_cursor: string | null };

export const getProfile = (walletId: string) => backend<BusinessProfile>(`agent/profile?wallet_id=${walletId}`);
export const saveProfile = (walletId: string, answers: string[], version: number) =>
  backend<BusinessProfile>("agent/profile", {
    method: "PATCH", body: { wallet_id: walletId, answers, expected_version: version },
  });
export const getChat = (walletId: string, cursor?: string) =>
  backend<ChatPage>(`agent/chat?wallet_id=${walletId}${cursor ? `&cursor=${cursor}` : ""}`);
export const sendChat = (walletId: string, message: string, requestId: string) =>
  backend<Exchange>("agent/chat", {
    method: "POST", body: { wallet_id: walletId, message, request_id: requestId },
  });

export const chatTurns = (items: Exchange[]) => items.flatMap((item) => [
  { role: "user" as const, content: item.message },
  { role: "assistant" as const, content: item.reply },
]);
