import {useTranslation} from "next-i18next";
import environments from "@app/configs/environments";
import Image from "next/image";
import BannerImage from "@app/assets/BannerImage.svg";
import FlexRowContainer from "@app/containers/landingpage/FlexRowContainer";
import ButtonRenderer from "@app/components/ui/ButtonRenderer";
import {useRouter} from "next/router";
import LandingPageSectionContainer from "@app/components/landingpage/LandingPageSectionContainer";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-13
 * Time: 14:34
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function Banner() {
    const {t} = useTranslation();

    const router = useRouter();

    return (
        <div className={"bg-[url('/background-7.svg')] bg-no-repeat bg-center bg-cover"}>
            <LandingPageSectionContainer sectionId={"banner"}>
                <FlexRowContainer>
                    <div className={"w-1/2 pt-16"}>
                        <div className={"font-bold text-7xl font-roboto mb-3"}>
                            {t('SLOGAN_TITLE')}
                        </div>
                        <div className={" font-roboto font-display text-gray-400 text-2xl mb-6"}>
                            {t("SLOGAN_DESCRIPTION")}
                        </div>
                        <ButtonRenderer buttonId={"button-wait-list"} onClick={() => router.push("#waitlist")}>
                            <p>{t("JOIN_WAITLIST")}</p>
                        </ButtonRenderer>
                    </div>
                    <div>
                        <Image src={BannerImage} className={"rounded-lg"} alt={"Forms"}/>
                    </div>
                </FlexRowContainer>
            </LandingPageSectionContainer>
        </div>
    );
}
