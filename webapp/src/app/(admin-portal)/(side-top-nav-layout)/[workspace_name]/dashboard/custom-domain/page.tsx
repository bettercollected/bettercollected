import { Metadata } from 'next';
import CustomDomainClient from './_components/custom-domain-client';

export const metadata: Metadata = {
    title: 'Custom Domain'
};

export default function CustomDomainPage() {
    return <CustomDomainClient />;
}
