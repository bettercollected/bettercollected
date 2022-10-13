/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-12
 * Time: 19:18
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

import { useTranslation } from "next-i18next";
import Box from "@mui/material/Box";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import FormControl from "@mui/material/FormControl";
import Select from "@mui/material/Select";
import { useState } from "react";
import { useRouter } from "next/router";

import GoogleIcon from "@mui/icons-material/Google";
import IconsRender from "@app/components/ui/iconsRender";

const IconsArray = [
  {
    Icon: <GoogleIcon />,
    description: "Google",
  },
  {
    Icon: <GoogleIcon />,
    description: "Google",
  },
  {
    Icon: <GoogleIcon />,
    description: "Google",
  },
];

export default function LoginForm() {
  const { t } = useTranslation();

  const router = useRouter();

  const [language, setLanguage] = useState(router.locale);

  const handleLanguageChange = (nextLocale: string) => {
    router
      .push({ pathname: router.pathname, query: router.query }, router.asPath, {
        locale: nextLocale,
      })
      .then((_) => setLanguage(nextLocale));
  };

  const renderHeader = () => (
    <div className={"flex justify-between mb-24"}>
      <div className="flex justify-center items-center">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="w-10 h-17 text-blue-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path d="M12 14l9-5-9-5-9 5 9 5z" />
          <path d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z" />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14zm-4 6v-7.5l4-2.222"
          />
        </svg>
        <div className={"font-semibold text-2xl"}>BetterCollected</div>
      </div>
      <div>
        <FormControl>
          <Select
            value={language}
            onChange={(event) =>
              handleLanguageChange(event.target.value as string)
            }
          >
            <MenuItem value={"en"}>EN</MenuItem>
            <MenuItem value={"de"}>DE</MenuItem>
          </Select>
        </FormControl>
      </div>
    </div>
  );

  return (
    <div className="flex justify-center sm:p-12 md:w-1/2">
      <div className="w-full">
        {renderHeader()}
        <div className={"mb-6"}>
          <div className={"font-normal text-2xl"}>
            {t("LOGIN").toUpperCase()}
          </div>
          <p className={"text-gray-500"}>{t("LOGIN_TITLE_SLOGAN")}</p>
        </div>

        <IconsRender IconsArray={IconsArray} />

        <p className={"flex justify-center font-normal text-gray-500"}>
          {t("OR")}
        </p>

        <div className="mt-4">
          <label className="block text-sm">{t("EMAIL")}</label>
          <input
            type="email"
            className="w-full px-4 py-2 text-sm border rounded-md focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
            placeholder={t("EMAIL_ADDRESS")}
          />
        </div>
        <button className="block w-full px-4 py-2 mt-4 text-sm font-medium leading-5 text-center text-white transition-colors duration-150 bg-[#4441d6] border border-transparent rounded-lg active:bg-blue-600 hover:bg-blue-700 focus:outline-none focus:shadow-outline-blue">
          {t("LOGIN")}
        </button>

        <div className="mt-4 text-center">
          <p className="text-sm">
            Donot have an account yet?{" "}
            <a
              href="@app/pages/Login/login#"
              className="text-blue-600 hover:underline"
            >
              {" "}
              Sign up
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
