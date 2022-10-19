import HeadingRenderer from "@app/components/ui/HeadingRenderer";
import {useTranslation} from "next-i18next";
import FormRenderer from "@app/components/ui/FormRenderer";
import {useState} from "react";
import FormInput from "@app/components/ui/FormInput";
import ContactImage from '@app/assets/contact_us.svg';
import Image from 'next/image';

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 15:04
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function ContactUs() {
    const {t} = useTranslation();

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
        setFormFields({...formFields, [id]: value});
    };

    return (
        <div className={"m-2 p-52 pb-5 pt-5 mb-3"}>
            <HeadingRenderer description={t("CONTACT_US_DESCRIPTION")}>
                {t('CONTACT_US')}
            </HeadingRenderer>
            <div className={"flex items-center shadow-md"}>
                <div>
                    <Image src={ContactImage} alt={"Contact us"}/>
                </div>

                <div className={"flex-shrink-0 flex-grow-0 basis-[50%]"}>
                    <h2 className={"text-roboto text-3xl text-center"}>Enter your information</h2>
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
                                className="resize rounded-md border h-[100px]"
                                onChange={(e) =>
                                    handleAllFieldChanges(e.currentTarget.id, e.target.value)
                                }
                            ></textarea>
                        </div>
                    </FormRenderer>
                </div>
            </div>
        </div>
    );
}
