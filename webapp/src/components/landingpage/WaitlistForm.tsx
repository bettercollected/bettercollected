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
import FormRenderer from "@app/components/ui/FormRenderer";
import FormInput from "@app/components/ui/FormInput";

export default function WaitlistForm() {
  const { t } = useTranslation();

  const [formFields, setFormFields] = useState({
    firstname: "",
    lastname: "",
    email: "",
  });

  //TODO api call
  const handleSubmit = (e: any) => {
    e.preventDefault();
    console.log("submit:", formFields);
  };

  const handleAllFieldChanges = (id: string, value: any) => {
    setFormFields({ ...formFields, [id]: value });
  };

  const renderFormDescription = () => (
    <>
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
    </>
  );

  return (
    <div id={"waitlist"}>
      <LandingPageContainer>
        <div>
          <Image src={BannerImage} alt={"Forms"} />
        </div>
        <FormRenderer handleSubmit={handleSubmit}>
          {renderFormDescription()}
          <div className={"mb-4"}>
            <div className={"flex mb-4 gap-3"}>
              <FormInput
                label={"Your First Name"}
                placeholder={"Enter your first name"}
                id={"firstname"}
                handleChange={handleAllFieldChanges}
              />
              <FormInput
                label={"Your Last Name"}
                placeholder={"Enter your last name"}
                id={"lastname"}
                handleChange={handleAllFieldChanges}
              />
            </div>
            <FormInput
              label={"Email Address"}
              placeholder={"Enter your email address"}
              id={"email"}
              handleChange={handleAllFieldChanges}
            />
          </div>
        </FormRenderer>
      </LandingPageContainer>
    </div>
  );
}
