import {serverSideTranslations} from "next-i18next/serverSideTranslations";
import img1 from '@app/assets/carousel/1.jpg';
import img2 from '@app/assets/carousel/1.jpg';
import img3 from '@app/assets/carousel/1.jpg';
import LocalCarousel from "@app/components/ui/carousel";
import LoginForm from "@app/components/login/login-form";
import {useEffect} from "react";
import {useRouter} from "next/router";
import Head from "next/head";

export default function LoginContainer(props: any) {

    const router = useRouter();

    useEffect(()=>{
        const locale = router.locale;
        router.push(`/${locale}${router.pathname}`).then(r=>r)
    },[])

    return (
        <div className="flex items-center min-h-screen bg-gray-50">
            <Head>
                <title>Login</title>
            </Head>
            <div className="flex-1 min-h-screen min-w-screen bg-white rounded-lg shadow-xl">
                <div className="flex flex-col min-h-screen md:flex-row">
                    <LocalCarousel ImagesArray={[img1, img2, img3]}/>
                    <LoginForm/>
                </div>
            </div>
        </div>
    );
}

export async function getServerSideProps({locale}: any) {
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
        },
    };
}