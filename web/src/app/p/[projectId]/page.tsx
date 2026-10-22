import { Suspense } from "react";
import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";
import { Workspace } from "@/components/chat/Workspace";

// Cache Components: the param is only known per request, so it is read inside Suspense.
export default function ProjectPage({ params }: PageProps<"/p/[projectId]">) {
  return (
    <Suspense fallback={<div className="min-h-dvh" />}>
      <Project params={params} />
    </Suspense>
  );
}

async function Project({ params }: Pick<PageProps<"/p/[projectId]">, "params">) {
  const { projectId } = await params;
  return (
    <AuthGate>
      <AppShell>
        <Workspace projectId={projectId} />
      </AppShell>
    </AuthGate>
  );
}
