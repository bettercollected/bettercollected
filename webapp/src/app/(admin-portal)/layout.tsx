import environments from "@app/configs/environments";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

export default async function AdminPortalLayout({ children }: { children: React.ReactNode }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hadAdminDomain = host === environments.ADMIN_DOMAIN;

    if (!hadAdminDomain) {
        notFound();
    }

    return (
        <div>
            {children}
        </div>
    );
}