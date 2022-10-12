import {serverSideTranslations} from "next-i18next/serverSideTranslations";
import {useTranslation} from "next-i18next";
import {Carousel} from 'react-responsive-carousel';
import img1 from '@app/assets/carousel/1.jpg';
import img2 from '@app/assets/carousel/1.jpg';
import img3 from '@app/assets/carousel/1.jpg';
import LocalCarousel from "@app/components/ui/carousel";

export default function Login(props: any) {
    const {t} = useTranslation();

    const renderCarousel = () => (
        <div className="min-h-screen md:h-auto md:w-3/5">
            {LocalCarousel([img1, img2, img3])}
        </div>
    );

    const renderLoginForm = () => (
        <div className="flex items-center justify-center p-6 sm:p-12 md:w-1/2">
            <div className="w-full">
                <div className={"flex justify-center"}>
                    <div className="flex justify-center items-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-10 h-17 text-blue-600" fill="none"
                             viewBox="0 0 24 24" stroke="currentColor">
                            <path d="M12 14l9-5-9-5-9 5 9 5z"/>
                            <path
                                d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z"/>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                  d="M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14zm-4 6v-7.5l4-2.222"/>
                        </svg>
                        <div className={"font-semibold text-2xl"}>BetterCollected</div>
                    </div>
                </div>
                <h1 className="mb-4 text-2xl font-bold text-center text-gray-700">
                    {t('h1')}
                </h1>
                <div>
                    <label className="block text-sm">
                        Name
                    </label>
                    <input type="text"
                           className="w-full px-4 py-2 text-sm border rounded-md focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
                           placeholder="Name"/>
                </div>
                <div className="mt-4">
                    <label className="block text-sm">
                        Email
                    </label>
                    <input type="email"
                           className="w-full px-4 py-2 text-sm border rounded-md focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
                           placeholder="Email Address"/>
                </div>
                <div>
                    <label className="block mt-4 text-sm">
                        Password
                    </label>
                    <input
                        className="w-full px-4 py-2 text-sm border rounded-md focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
                        placeholder="Password" type="password"/>
                </div>
                <button
                    className="block w-full px-4 py-2 mt-4 text-sm font-medium leading-5 text-center text-white transition-colors duration-150 bg-blue-600 border border-transparent rounded-lg active:bg-blue-600 hover:bg-blue-700 focus:outline-none focus:shadow-outline-blue">
                    Sign up
                </button>

                <div className="mt-4 text-center">
                    <p className="text-sm">Donot have an account yet? <a href="src/pages/login#"
                                                                         className="text-blue-600 hover:underline"> Sign
                        up.</a></p>
                </div>
            </div>
        </div>
    );

    const mainContainer = () => (
        <div className="flex items-center min-h-screen bg-gray-50">
            <div className="flex-1 min-h-screen min-w-screen bg-white rounded-lg shadow-xl">
                <div className="flex flex-col min-h-screen md:flex-row">
                    {renderCarousel()}
                    {renderLoginForm()}
                </div>
            </div>
        </div>
    );

    return mainContainer();
}

export async function getServerSideProps({locale}: any) {
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
        },
    };
}