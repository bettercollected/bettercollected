import BrandLogo from "@app/assets/brand-logo.svg";
import HamburgerMenu from "@app/assets/hamburger-menu.svg";
import Image from "next/image";
import {useTranslation} from "next-i18next";
import LanguageChangeDropdownRenderer from "@app/components/landingpage/LanguageChangeDropdownRenderer";
import ThemeSwitcher from "@app/components/settings/theme-switcher";
import ButtonRenderer from "@app/components/ui/ButtonRenderer";
import {useRouter} from "next/router";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-13
 * Time: 13:05
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function Navbar() {
    const {t} = useTranslation();
    const router = useRouter();
    // bg-[#f5faff]
    return (
        <div className={"sticky top-0 z-50 h-[70px]"}>
            <div className={"p-2 pl-20 pr-20 flex justify-between"}>
                <div className={"flex items-center"}>
                    <div className={"font-bold text-2xl font-roboto tracking-widest"}>
                        Better<span className={"text-[#007AFF] tracking-widest"}>Collected.</span>
                    </div>
                </div>
                <div className={"flex items-center gap-6"}>
                    <LanguageChangeDropdownRenderer/>
                    {/*<ThemeSwitcher />*/}
                    <ButtonRenderer onClick={() => router.push("#waitlist")}>
                        <p>{t("JOIN_WAITLIST")}</p>
                    </ButtonRenderer>
                </div>
            </div>
        </div>
    );
}
