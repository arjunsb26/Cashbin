import { redirect } from "next/navigation";

/**
 * The register moved inside Books, where the rest of the finance side lives.
 * The old address still works, because it is written down in places this
 * codebase does not own.
 */
export default function AssetsPage() {
  redirect("/books/register");
}
