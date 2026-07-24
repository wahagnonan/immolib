import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { NotificationSettings } from "@/components/notifications/notification-settings";


export const metadata: Metadata = { title: "Notifications" };

export default function NotificationSettingsPage() {
  return (
    <AppShell>
      <NotificationSettings />
    </AppShell>
  );
}

