import Collaborators from '@app/components/member/collaborators';
import { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Members'
};

export default function Page() {
    return <Collaborators />;
}
