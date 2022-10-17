import { useTranslation } from "next-i18next";
import environments from "@app/configs/environments";
import Image from "next/image";
import BannerImage from "@app/assets/BannerImage.svg";
import LandingPageContainer from "@app/containers/landingpage/LandingPageContainer";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-13
 * Time: 14:34
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function Banner() {
  const { t } = useTranslation();

  return (
    <LandingPageContainer>
      <div className={"w-1/2 pt-40"}>
        <>
          <div className={"font-semibold text-6xl mb-3"}>
            {environments.COMPANY_NAME}.
          </div>
          <div
            className={
              "font-medium font-roboto font-display text-gray-400 text-2xl mb-3"
            }
          >
            {t("SLOGAN")}
          </div>
          <button
            className={
              "bg-[#007AFF] p-3 rounded-md text-white font-semibold font-lato hover:bg-[#967bd0]"
            }
          >
            <a href={"#waitlist"}>{t("JOIN_WAITLIST")}</a>
          </button>
        </>
      </div>
      <div>
        <Image src={BannerImage} alt={"Forms"} />
      </div>
    </LandingPageContainer>
  );
}
