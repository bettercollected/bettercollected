import Banner from '@app/components/homepage/banner';
import Features from '@app/components/homepage/features';
import Waitlist from '@app/components/homepage/waitlist';
import Footer from '@app/components/landingpage/Footer';
import Layout from '@app/layouts/_layout';

export default function HomeContainer() {
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
