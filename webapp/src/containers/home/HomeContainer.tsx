import { useEffect } from 'react';

import Cal, { getCalApi } from '@calcom/embed-react';

import Banner from '@app/components/homepage/banner';
import Features from '@app/components/homepage/features';
import Waitlist from '@app/components/homepage/waitlist';
import Footer from '@app/components/landingpage/Footer';
import Layout from '@app/layouts/_layout';

export default function HomeContainer() {
    useEffect(() => {
        (async function () {
            const cal = await getCalApi();
            cal('floatingButton', { calLink: 'bettercollected', buttonText: 'Request a demo', buttonColor: '#3B82F6' });
        })();
    }, []);
    return (
        <>
            <Layout className="min-h-full">
                <Banner />
                <Features />
                <Waitlist />
                <Footer />
            </Layout>
        </>
    );
}
