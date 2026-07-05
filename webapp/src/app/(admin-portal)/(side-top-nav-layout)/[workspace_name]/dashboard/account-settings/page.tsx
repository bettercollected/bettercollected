import { Metadata } from 'next';
import AccountSettingsClient from './_components/account-settings-client';

export const metadata: Metadata = {
    title: 'Account Settings'
};

export default function AccountSettingsPage() {
    return <AccountSettingsClient />;
}
