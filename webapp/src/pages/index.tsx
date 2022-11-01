import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import dynamic from 'next/dynamic';

import environments from '@app/configs/environments';
import { CompanyJsonDto } from '@app/models/dtos/customDomain';

const DashboardContainer = dynamic(() => import('@app/containers/dashboard/DashboardContainer'), { ssr: false });
const Banner = dynamic(() => import('@app/components/landingpage/Banner'), { ssr: false });
const Features = dynamic(() => import('@app/components/landingpage/Features'), { ssr: false });
const Footer = dynamic(() => import('@app/components/landingpage/Footer'), { ssr: false });
const Navbar = dynamic(() => import('@app/components/landingpage/Navbar'), { ssr: false });
const Payment = dynamic(() => import('@app/components/landingpage/Payment'), { ssr: false });

interface IHome {
    hasCustomDomain: boolean;
    companyJson: CompanyJsonDto | null;
}

const Home = ({ hasCustomDomain, companyJson }: IHome) => {
    if (hasCustomDomain) return <DashboardContainer companyJson={companyJson} />;

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
    const hasCustomDomain = !!environments.IS_CUSTOM_DOMAIN;
    let companyObj: CompanyJsonDto | null = null;
    try {
        if (hasCustomDomain && !!environments.CUSTOM_DOMAIN_JSON) {
            const json = await fetch(environments.CUSTOM_DOMAIN_JSON).catch((e) => e);
            companyObj = await json.json();
        }
    } catch (err) {
        console.error(err);
    }
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
            hasCustomDomain: hasCustomDomain && !!environments.CUSTOM_DOMAIN_JSON,
            companyJson: companyObj
        }
    };
}
