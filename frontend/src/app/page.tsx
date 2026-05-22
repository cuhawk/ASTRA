import { redirect } from "next/navigation";
import { apiServer } from "@/lib/api-server";
import { loginHref } from "@/lib/api";
import type { User } from "@/lib/types";

async function getUser(): Promise<User | null> {
  try {
    return await apiServer<User>("/auth/me");
  } catch {
    return null;
  }
}

export default async function LandingPage() {
  const user = await getUser();
  if (user) redirect("/runs");

  return (
    <div className="py-16 flex flex-col items-start gap-8">
      <h1 className="text-5xl font-bold tracking-tight text-emerald-400">
        ASTRA
      </h1>
      <p className="text-zinc-300 text-lg max-w-2xl leading-relaxed">
        Paste a URL or upload a <code className="text-emerald-300">.zip</code>{" "}
        of JavaScript. ASTRA crawls or unpacks it on the server, reconstructs
        original sources from sourcemaps, builds a framework-aware callgraph
        with taint tags, captures runtime coverage from a real Chrome session
        to label every function with which features actually execute it, and
        serves the result as an interactive graph you can query in cypher or
        natural language.
      </p>
      <a
        href={loginHref()}
        className="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded text-base font-medium"
      >
        Sign in with GitHub
      </a>
    </div>
  );
}
