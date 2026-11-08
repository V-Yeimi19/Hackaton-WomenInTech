/** Tipos de dominio derivados del contrato OpenAPI del backend (`npm run api:types`). */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Wallet = Schemas["WalletOut"];
export type WalletList = Schemas["WalletListResponse"];
export type WalletCreate = Schemas["WalletCreate"];
export type WalletArchive = Schemas["WalletArchiveResponse"];
export type Movement = Schemas["MovementOut"];
export type MovementList = Schemas["MovementListResponse"];
export type Operation = Schemas["OperationResponse"];
export type YapeoRequest = Schemas["YapeoRequest"];
export type TransferRequest = Schemas["WalletTransferRequest"];
export type Category = NonNullable<YapeoRequest["category"]>;
export type CounterpartyType = YapeoRequest["counterparty"]["type"];
