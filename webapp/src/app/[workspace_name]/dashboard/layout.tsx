import ConditionalLayout from "./_components/conditional-layout";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    return <ConditionalLayout>{children}</ConditionalLayout>;
}