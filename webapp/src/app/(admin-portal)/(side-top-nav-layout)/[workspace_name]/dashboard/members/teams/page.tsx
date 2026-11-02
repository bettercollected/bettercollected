import { Metadata } from 'next';

import Teams from '@app/components/member/teams';

export const metadata: Metadata = {
    title: 'Teams'
};

export default function Page() {
    return <Teams />;
}
