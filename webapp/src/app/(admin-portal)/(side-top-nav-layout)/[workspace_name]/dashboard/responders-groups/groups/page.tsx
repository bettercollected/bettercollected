import { Metadata } from 'next';
import GroupsClient from './_components/groups-client';

export const metadata: Metadata = {
    title: 'Groups'
};

export default function GroupsPage() {
    return <GroupsClient />;
}
