import HeadingRenderer from "@app/components/ui/HeadingRenderer";
import { useTranslation } from "next-i18next";
import FormRenderer from "@app/components/ui/FormRenderer";
import { useState } from "react";
import FormInput from "@app/components/ui/FormInput";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 15:04
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function ContactUs() {
  const { t } = useTranslation();

  const [formFields, setFormFields] = useState({
    fullname: "",
    email: "",
    message: "",
  });

  //TODO api call
  const handleSubmit = (e: any) => {
    e.preventDefault();
    console.log("submit:", formFields);
  };

  const handleAllFieldChanges = (id: string, value: any) => {
    setFormFields({ ...formFields, [id]: value });
  };

  return (
    <>
      <HeadingRenderer description={t("CONTACT_US_DESCRIPTION")}>
        {t('CONTACT_US')}
      </HeadingRenderer>
      <div className={"flex mx-auto rounded-md shadow-md"}>
        <div className={"flex flex-col md:flex-row"}>
          <div className={"h-32 md:h-auto md:w-1/2"}>
            <img
              className="object-cover w-full h-full"
              src="https://source.unsplash.com/user/erondu/1600x900"
              alt="img"
            />
          </div>

          <FormRenderer handleSubmit={handleSubmit}>
            <FormInput
              label={"Your Name"}
              placeholder={"Your full name"}
              id={"fullname"}
              handleChange={handleAllFieldChanges}
            />
            <FormInput
              label={"Email Address"}
              placeholder={"Enter your email address"}
              id={"email"}
              handleChange={handleAllFieldChanges}
            />
            <div className={"flex flex-col mb-3"}>
              <label
                className={"block text-gray-700 text-sm font-normal mb-2"}
                htmlFor={"message"}
              >
                Message
              </label>
              <textarea
                id={"message"}
                className="resize rounded-md border"
                onChange={(e) =>
                  handleAllFieldChanges(e.currentTarget.id, e.target.value)
                }
              ></textarea>
            </div>
          </FormRenderer>
        </div>
      </div>
    </>
  );
}
