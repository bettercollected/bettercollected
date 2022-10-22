import {useTranslation} from "next-i18next";
import environments from "@app/configs/environments";
import Image from "next/image";
import BannerImage from "@app/assets/BannerImage.svg";
import FlexRowContainer from "@app/containers/landingpage/FlexRowContainer";
import ButtonRenderer from "@app/components/ui/ButtonRenderer";
import {useRouter} from "next/router";
import LandingPageSectionContainer from "@app/components/landingpage/LandingPageSectionContainer";
import useDimension from "@app/hooks/useDimension";
import FormInput from "@app/components/ui/FormInput";
import {useState} from "react";
import Iframe from "@app/components/landingpage/Iframe";
import Link from "next/link";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-13
 * Time: 14:34
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function Banner() {
    const {t} = useTranslation();
    const [email, setEmail] = useState("");

    const [iFrame, setIframe] = useState(false);
    const router = useRouter();

    const handleChange = (id: string, value: any) => {
        setEmail(value)
    }

    const handleSubmit = () => {
        // const myInit:any = {
        //     method: 'GET',
        //     mode: 'cors',
        //     headers: [
        //     ['Content-Type', 'application/x-www-form-urlencoded'],
        //     ['Content-Type', 'multipart/form-data'],
        //     ['Content-Type', 'text/plain'],
        // ],
        //     cache: 'default',
        // };
        // fetch(`https://docs.google.com/forms/d/e/1FAIpQLSc-OA5vBjBLYm2xN2ZVxDuxqqrmwSHKAqAgv6QrF1TwIWKMow/viewform?emailAddress=${email}`,myInit)
        //     .then(res => console.log("res"))
        //     .finally(() => {
        //         setIframe(true)
        //     })
        // setIframe(true)
        router.push('/waitlistForms')
    }

    const shouldButtonDisable = () => {
        const pattern = /^\w+@[a-zA-Z_]+?\.[a-zA-Z]{2,3}$/;
        return !email.match(pattern);
    }

    return (
        <>
            {iFrame && <Iframe formUrl={`${environments.WAILIST_URL}&emailAddress=${email}`}
                               handleClose={() => setIframe(false)}/>}
            <div className={"sm:bg-white lg:bg-[url('/background-7.svg')] lg:bg-no-repeat lg:bg-cover"}>
                <LandingPageSectionContainer sectionId={"banner"}>
                    <FlexRowContainer>
                        <div className={"w-full md:w-full lg:w-1/2"}>
                            <div className={"font-bold text-2xl sm:text-4xl md:text-5xl lg:text-7xl font-roboto mb-3"}>
                                {t('SLOGAN_TITLE')}
                            </div>
                            <div className={"font-roboto font-display text-gray-400 text-lg sm:text-2xl mb-6"}>
                                {t("SLOGAN_DESCRIPTION")}
                            </div>

                            <div className={"flex flex-col lg:flex-row lg:items-center gap-4"}>
                                {/*<FormInput*/}
                                {/*    label={""}*/}
                                {/*    placeholder={t("EMAIL_ADDRESS")}*/}
                                {/*    id={"email"}*/}
                                {/*    handleChange={handleChange}*/}
                                {/*/>*/}
                                <a href="/waitlist" target="_blank">
                                    <div
                                        // onClick={handleSubmit}
                                        className={"cursor-pointer shadow-md hover:bg-[#4da2ff] text-center p-3 mb-2 md:p-4 md:pt-2 md:pb-2 text-white rounded-md bg-[#007AFF]"}>
                                        {t("BECOME_A_BETTER_COLLECTOR")}
                                    </div>
                                </a>
                            </div>
                        </div>
                        <div><Image src={BannerImage} className={"rounded-lg"} alt={"Forms"}/></div>
                    </FlexRowContainer>
                </LandingPageSectionContainer>
            </div>
        </>
    );
}
