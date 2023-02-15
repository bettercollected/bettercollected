import { useEffect } from 'react';

import Cal, { getCalApi } from '@calcom/embed-react';

import Footer from '@app/components/landingpage/Footer';
import Banner from '@app/components/landingpage/banner';
import Features from '@app/components/landingpage/features';
import WaitList from '@app/components/landingpage/waitList';
import Layout from '@app/layouts/_layout';

export default function LandingPage() {
    useEffect(() => {
        (async function () {
            const cal: any = await getCalApi();
            cal('floatingButton', { calLink: 'bettercollected', buttonText: 'Request a demo', buttonColor: '#3B82F6' });
        })();
    }, []);
    return (
        <>
            <Layout className="min-h-full" showNavbar>
                <Banner />
                <Features />
                <WaitList />
                <Footer />
            </Layout>
        </>
    );
}
