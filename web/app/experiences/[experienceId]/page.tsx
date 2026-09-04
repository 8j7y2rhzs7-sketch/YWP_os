import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { DecisionEngineStage } from "../../components/DecisionEngineStage";

const CHECKOUT =
  process.env.NEXT_PUBLIC_WHOP_CHECKOUT_URL ??
  "https://whop.com/checkout/plan_MwJ2qcFxmvqDY";
const PRODUCT_ID = process.env.WHOP_PRODUCT_ID ?? "prod_NuPQUAGoibkpW";

export default async function ExperiencePage({
  params,
}: {
  params: Promise<{ experienceId: string }>;
}) {
  const { experienceId } = await params;
  const incoming = await headers();
  const api =
    process.env.YWP_API_INTERNAL_URL ?? "http://localhost:8000/api/v1";
  const token = incoming.get("x-whop-user-token") ?? "";
  const response = await fetch(`${api.replace(/\/$/, "")}/whop/gate`, {
    headers: token ? { "x-whop-user-token": token } : {},
    cache: "no-store",
  });
  const gate = (await response.json().catch(() => ({}))) as {
    has_access?: boolean;
    checkout_url?: string;
  };
  if (!gate.has_access) {
    redirect(gate.checkout_url || CHECKOUT);
  }

  return (
    <DecisionEngineStage
      experienceId={experienceId}
      productId={PRODUCT_ID}
      hasAccess={true}
    />
  );
}
