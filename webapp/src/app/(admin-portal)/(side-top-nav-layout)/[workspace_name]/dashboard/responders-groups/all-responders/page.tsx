import { Metadata } from 'next';
import AllRespondersClient from './_components/all-responders-client';

export const metadata: Metadata = {
    title: 'Responders'
};

export default function AllRespondersPage() {
    return <AllRespondersClient />;
}
