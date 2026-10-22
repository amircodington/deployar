import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";
import { Workspace } from "@/components/chat/Workspace";

export default function Home() {
  return (
    <AuthGate>
      <AppShell>
        <Workspace />
      </AppShell>
    </AuthGate>
  );
}
