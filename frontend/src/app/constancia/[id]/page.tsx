import { ReceiptScreen } from "@/features/receipts/ReceiptScreen";

export default async function ConstanciaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReceiptScreen movementId={id} />;
}
