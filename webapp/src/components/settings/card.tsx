export default function SettingsCard({ className = '', children }: any) {
    return <div className={'flex flex-col bg-white rounded p-10 space-y-4 mt-10' + ' ' + className}>{children}</div>;
}

export function FormSettingsCard({ className = '', children }: any) {
    return <SettingsCard className="!p-6 !mt-5">{children}</SettingsCard>;
}
