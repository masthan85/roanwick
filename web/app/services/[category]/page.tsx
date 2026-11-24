import { redirect } from "next/navigation";

export function generateStaticParams() {
  return [{ category: "home-cleaning" }];
}

export default function CategoryPage() {
  redirect("/services");
}
