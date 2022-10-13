import BrandLogo from "@app/assets/brand-logo.svg";
import HamburgerMenu from "@app/assets/hamburger-menu.svg";
import Image from "next/image";
import { useTranslation } from "next-i18next";
import LanguageChangeDropdownRenderer from "@app/components/landingpage/LanguageChangeDropdownRenderer";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-13
 * Time: 13:05
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function Navbar() {
  const { t } = useTranslation();
  return (
    <div className={"sticky"}>
      <div className={"ml-6 mr-6 mb-6 p-1 flex justify-between"}>
        <div className={"flex items-center"}>
          <Image
            src={BrandLogo}
            height={45}
            width={45}
            alt={"BetterCollected"}
          />
        </div>
        <div className={"flex items-center gap-6"}>
          <button
            className={
              "border-solid border-[1px] p-2 rounded-md border-[#efefef]"
            }
          >
            {t("LOGIN")}
          </button>
          <Image src={HamburgerMenu} height={30} width={30} alt={"☰"} />
          <LanguageChangeDropdownRenderer />
        </div>
      </div>
    </div>
  );
}
