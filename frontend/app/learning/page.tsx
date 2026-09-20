import { redirect } from "next/navigation";

/**
 * Learning folded into Trends, where the accuracy and the cost per toss sit
 * beside what was actually thrown away. The old address still works.
 */
export default function LearningPage() {
  redirect("/trends");
}
