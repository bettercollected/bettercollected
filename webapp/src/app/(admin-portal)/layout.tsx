import environments from "@app/configs/environments";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { StaffLanguageProvider } from "@app/components/staff-language-provider";

export default async function AdminPortalLayout({ children }: { children: React.ReactNode }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hadAdminDomain = host === environments.DASHBOARD_DOMAIN;

    if (!hadAdminDomain) {
        notFound();
    }

    return (
        <StaffLanguageProvider>
            {/* The creator app's colour theme (tailwind.css, "App theme scope"); respondent routes never carry it. */}
            <div data-app-theme="daybreak">
                {children}
            </div>
        </StaffLanguageProvider>
    );
}