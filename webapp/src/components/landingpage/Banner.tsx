import {useTranslation} from "next-i18next";
import environments from "@app/configs/environments";
import Image from "next/image";
import BannerImage from "@app/assets/BannerImage.svg";
import LandingPageContainer from "@app/containers/landingpage/LandingPageContainer";
import ButtonRenderer from "@app/components/ui/ButtonRenderer";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-13
 * Time: 14:34
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function Banner() {
    const {t} = useTranslation();

    return (
        <div className={"bg-[#F5F2FD]"}>
            <div className={"min-h-screen box-border p-52 pb-0 pt-5"}>
                <LandingPageContainer>
                    <div className={"w-1/2 pt-40"}>
                        <div className={"font-semibold text-7xl font-roboto mb-3"}>
                            Work with your favorite form builders.
                        </div>
                        <div
                            className={
                                "font-medium font-roboto font-display text-gray-400 text-2xl mb-3"
                            }
                        >
                            {t("SLOGAN")}
                        </div>
                        <ButtonRenderer>
                            <a href={"#waitlist"}>{t("JOIN_WAITLIST")}</a>
                        </ButtonRenderer>
                    </div>
                    <div>
                        <Image src={BannerImage} alt={"Forms"}/>
                    </div>
                </LandingPageContainer>
            </div>
        </div>
    );
}
