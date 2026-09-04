import { DecisionEngineStage } from "./components/DecisionEngineStage";

const PRODUCT_ID = process.env.WHOP_PRODUCT_ID ?? "prod_NuPQUAGoibkpW";
const CHECKOUT =
  process.env.NEXT_PUBLIC_WHOP_CHECKOUT_URL ??
  "https://whop.com/checkout/plan_MwJ2qcFxmvqDY";

export default function HomePage() {
  return (
    <DecisionEngineStage
      experienceId="home"
      productId={PRODUCT_ID}
      hasAccess={false}
      checkoutUrl={CHECKOUT}
    />
  );
}

export const dynamic = "force-static";
