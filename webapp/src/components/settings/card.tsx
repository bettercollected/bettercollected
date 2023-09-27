export default function SettingsCard({ className = '', children }: any) {
    return <div className={'flex flex-col bg-white rounded space-y-4 mt-10' + ' ' + className}>{children}</div>;
}

export function FormSettingsCard({ className = '', children }: any) {
    return <SettingsCard className={`!mt-4 ${className}`}>{children}</SettingsCard>;
}
