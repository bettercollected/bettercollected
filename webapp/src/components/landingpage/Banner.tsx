import {useTranslation} from "next-i18next";
import environments from "@app/configs/environments";
import Image from "next/image";
import BannerImage from "@app/assets/BannerImage.svg";
import LandingPageContainer from "@app/containers/landingpage/LandingPageContainer";
import ButtonRenderer from "@app/components/ui/ButtonRenderer";
import {useRouter} from "next/router";

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
        <div className={"bg-[#f5faff]"}>
            <div className={"min-h-screen box-border p-52 pb-0 pt-5"}>
                <LandingPageContainer>
                    <div className={"w-1/2 pt-40"}>
                        <div className={"font-semibold text-6xl font-roboto mb-3"}>
                            Work with your favorite form builders.
                        </div>
                        <div
                            className={
                                " font-roboto font-display text-gray-400 text-2xl mb-6"
                            }
                        >
                            {t("SLOGAN")}
                        </div>
                        <ButtonRenderer onClick={() => router.push("#waitlist")}>
                            <p>{t("JOIN_WAITLIST")}</p>
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
