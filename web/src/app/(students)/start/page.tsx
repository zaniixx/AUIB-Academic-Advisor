import type { Metadata } from "next";
import { StartWizard } from "@/components/start/StartWizard";

export const metadata: Metadata = { title: "Set up your plan" };

export default function StartPage() {
  return <StartWizard />;
}
