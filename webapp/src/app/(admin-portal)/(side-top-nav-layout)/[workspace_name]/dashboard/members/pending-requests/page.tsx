import Invitations from '@app/components/member/invitations';
import { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Pending Request'
};

export default function Page() {
    return <Invitations />;
}
