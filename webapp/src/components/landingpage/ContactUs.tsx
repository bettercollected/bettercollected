import HeadingRenderer from "@app/components/ui/HeadingRenderer";
import { useTranslation } from "next-i18next";

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 15:04
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function ContactUs() {
  const { t } = useTranslation();
  return (
    <>
      <HeadingRenderer description={t("CONTACT_US_DESCRIPTION")}>
        Contact Us
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
          <div className={"flex justify-center p-6"}>
            <form>
              <div className={"mb-4"}>
                <div className={"flex flex-col mb-3"}>
                  <label
                    className={"block text-gray-700 text-sm font-normal mb-2"}
                    htmlFor={"fullname"}
                  >
                    Your Name
                  </label>
                  <input
                    className="border text-gray-900 text-sm rounded-lg w-full p-2.5"
                    id={"fullname"}
                    type="text"
                    placeholder="Your full name"
                  />
                </div>

                <div className={"flex flex-col mb-3"}>
                  <label
                    className={"block text-gray-700 text-sm font-normal mb-2"}
                    htmlFor={"email"}
                  >
                    Email address
                  </label>
                  <input
                    className="border text-gray-900 text-sm rounded-lg w-full p-2.5"
                    id={"email"}
                    type="text"
                    placeholder="Enter your email"
                  />
                </div>
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
                  ></textarea>
                </div>
                <button
                  className="bg-blue-500 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                  type="submit"
                >
                  Send Message
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
}
