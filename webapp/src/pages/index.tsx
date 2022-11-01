import type { NextPage } from 'next';
import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import dynamic from 'next/dynamic';

import environments from '@app/configs/environments';

const Banner = dynamic(() => import('@app/components/landingpage/Banner'), { ssr: false });
const Features = dynamic(() => import('@app/components/landingpage/Features'), { ssr: false });
const Footer = dynamic(() => import('@app/components/landingpage/Footer'), { ssr: false });
const Navbar = dynamic(() => import('@app/components/landingpage/Navbar'), { ssr: false });
const Payment = dynamic(() => import('@app/components/landingpage/Payment'), { ssr: false });

const Home: NextPage = (props: any) => {
    const hasCustomDomain = !!props?.IS_CUSTOM_DOMAIN;

    if (hasCustomDomain) return <h1 className="text-red-500">Public dashboard of forms.sireto.io</h1>;

    return (
        <>
            <Navbar />
            <Banner />
            {/*<WaitlistForm/>*/}
            <Features />
            {/*<TimelineContainer/>*/}
            <Payment />
            {/*<ContactUs/>*/}
            <Footer />
        </>
    );
};

export default Home;

export async function getServerSideProps({ locale }: any) {
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
            IS_CUSTOM_DOMAIN: environments.IS_CUSTOM_DOMAIN
        }
    };
}
