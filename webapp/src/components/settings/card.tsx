import { FORM_CARD } from '@app/components/form/form-page';

export default function SettingsCard({ className = '', children }: any) {
    return <div className={'flex flex-col bg-white rounded space-y-4 mt-10' + ' ' + className}>{children}</div>;
}

export function FormSettingsCard({ className = '', children }: any) {
    // a form page's card (components/form/form-page.tsx): surface, strong hairline, 16 px (24 px from sm) inside
    return <div className={`flex flex-col gap-4 ${FORM_CARD} ${className}`}>{children}</div>;
}
