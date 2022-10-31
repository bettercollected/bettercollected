import type { NextPage } from 'next';
import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import Head from 'next/head';

import Advertising from '@app/components/landingpage/Advertising';
import Banner from '@app/components/landingpage/Banner';
import ContactUs from '@app/components/landingpage/ContactUs';
import Features from '@app/components/landingpage/Features';
import Footer from '@app/components/landingpage/Footer';
import Navbar from '@app/components/landingpage/Navbar';
import Payment from '@app/components/landingpage/Payment';
import TimelineContainer from '@app/components/landingpage/TimelineContainer';
import WaitlistForm from '@app/components/landingpage/WaitlistForm';

const Home: NextPage = () => {
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
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de']))
        }
    };
}
