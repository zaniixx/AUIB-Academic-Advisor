import type { Metadata } from "next";
import { AdvisorDocument } from "@/components/plan/AdvisorDocument";

// The browser offers this title as the PDF's file name.
export const metadata: Metadata = { title: "Plan for my advisor" };

export default function AdvisorDocumentPage() {
  return <AdvisorDocument />;
}
