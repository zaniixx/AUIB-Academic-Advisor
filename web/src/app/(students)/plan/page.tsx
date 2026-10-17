import type { Metadata } from "next";
import { PlanDashboard } from "@/components/plan/PlanDashboard";

export const metadata: Metadata = { title: "My plan" };

export default function PlanPage() {
  return <PlanDashboard />;
}
