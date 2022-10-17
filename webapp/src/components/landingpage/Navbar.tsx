import BrandLogo from "@app/assets/brand-logo.svg";
import HamburgerMenu from "@app/assets/hamburger-menu.svg";
import Image from "next/image";
import { useTranslation } from "next-i18next";
import LanguageChangeDropdownRenderer from "@app/components/landingpage/LanguageChangeDropdownRenderer";
import ThemeSwitcher from "@app/components/settings/theme-switcher";

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
    <div className={"sticky top-0 z-50"}>
      <div className={"p-48 mb-6 pb-2 pt-2 flex justify-between"}>
        <div className={"flex items-center"}>
          <Image
            src={BrandLogo}
            height={45}
            width={45}
            alt={"BetterCollected"}
          />
        </div>
        <div className={"flex items-center gap-6"}>
          {/*<ThemeSwitcher />*/}
          <button
            className={
              "border-solid border-[1px] p-2 rounded-md border-[#efefef]"
            }
          >
            <a href={"#waitlist"}>{t("JOIN_WAITLIST")}</a>
          </button>
          {/*<Image src={HamburgerMenu} height={30} width={30} alt={"☰"} />*/}
          <LanguageChangeDropdownRenderer />
        </div>
      </div>
    </div>
  );
}
