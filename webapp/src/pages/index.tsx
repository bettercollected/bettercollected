import type {NextPage} from "next";
import Navbar from "@app/components/landingpage/Navbar";
import {serverSideTranslations} from "next-i18next/serverSideTranslations";
import Banner from "@app/components/landingpage/Banner";
import Features from "@app/components/landingpage/Features";
import WaitlistForm from "@app/components/landingpage/WaitlistForm";
import ContactUs from "@app/components/landingpage/ContactUs";
import TimelineContainer from "@app/components/landingpage/TimelineContainer";
import Payment from "@app/components/landingpage/Payment";
import Head from "next/head";
import Footer from "@app/components/landingpage/Footer";
import Advertising from "@app/components/landingpage/Advertising";

const Home: NextPage = () => {
    return (
        <>
            <Navbar/>
            <Banner/>
            {/*<WaitlistForm/>*/}
            <Features/>
            {/*<TimelineContainer/>*/}
            <Payment/>
            {/*<ContactUs/>*/}
            <Footer/>
        </>
    );
};

export default Home;

export async function getServerSideProps({locale}: any) {
    return {
        props: {
            ...(await serverSideTranslations(locale, ["common"], null, ["en", "de"])),
        },
    };
}
