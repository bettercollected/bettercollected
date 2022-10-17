/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 13:25
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import LandingPageContainer from "@app/containers/landingpage/LandingPageContainer";
import environments from "@app/configs/environments";
import Image from "next/image";
import BannerImage from "@app/assets/BannerImage.svg";
import { useTranslation } from "next-i18next";
import { useState } from "react";

export default function WaitlistForm() {
  const { t } = useTranslation();

  const [formFields, setFormFields] = useState({
    first_name: "Rupan",
    last_name: "",
    email: "",
  });

  //TODO api call
  const handleSubmit = (e: any) => {
    e.preventDefault();
    console.log("submit:", formFields);
  };

  return (
    <div id={"waitlist"}>
      <LandingPageContainer>
        <div>
          <Image src={BannerImage} alt={"Forms"} />
        </div>
        <form
          className={"shadow-xl rounded-md mb-4 p-6 "}
          onSubmit={handleSubmit}
        >
          <div className={"font-semibold text-2xl text-blue-500 mb-3"}>
            Get early access!
          </div>
          <div
            className={
              "font-medium font-roboto font-display text-gray-400 text-xl mb-3"
            }
          >
            Be one of the first to create a profile and claim a basic plan for{" "}
            <b>free</b>.
          </div>

          <div className={"mb-4"}>
            <div className={"flex mb-4"}>
              <div className={"flex flex-col"}>
                <label
                  className={"block text-gray-700 text-sm font-normal mb-2"}
                  htmlFor={"firstname"}
                >
                  First Name
                </label>
                <input
                  className="shadow appearance-none w-3/4 border rounded py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                  id={"firstname"}
                  type="text"
                  placeholder="First name"
                  onChange={(e) =>
                    setFormFields({
                      ...formFields,
                      first_name: e.currentTarget.value,
                    })
                  }
                />
              </div>

              <div className={"flex flex-col"}>
                <label
                  className={"block text-gray-700 text-sm font-normal mb-2"}
                  htmlFor={"lastname"}
                >
                  Last Name
                </label>
                <input
                  className="shadow appearance-none w-3/4 border rounded py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                  id={"lastname"}
                  type="text"
                  placeholder="Last name"
                  onChange={(e) =>
                    setFormFields({
                      ...formFields,
                      last_name: e.currentTarget.value,
                    })
                  }
                />
              </div>
            </div>
            <div className={"flex flex-col mb-4"}>
              <label
                className={"block text-gray-700 text-sm font-normal mb-2"}
                htmlFor={"email"}
              >
                Email Address
              </label>
              <input
                className="shadow appearance-none border rounded py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                id={"email"}
                type="text"
                placeholder="Email address"
                onChange={(e) =>
                  setFormFields({ ...formFields, email: e.currentTarget.value })
                }
              />
            </div>
            <button
              className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
              type="submit"
            >
              Submit
            </button>
          </div>
        </form>
      </LandingPageContainer>
    </div>
  );
}
