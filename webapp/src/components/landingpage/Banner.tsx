import { useTranslation } from "next-i18next";

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
    <div
      className={"p-6 pt-40 pb-40 bg-gradient-to-r from-[#101e2e] to-[#2e5684]"}
    >
      <div className={"w-1/2"}>
        <div className={"font-semibold font-poppins text-6xl text-white mb-6"}>
          Better Collected.
        </div>
        <div
          className={
            "font-medium font-roboto font-display text-gray-400 text-2xl"
          }
        >
          {t("SLOGAN")}
        </div>
      </div>
    </div>
  );
}
