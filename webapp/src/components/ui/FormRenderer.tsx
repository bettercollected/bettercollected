/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 16:01
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import {useTranslation} from "next-i18next";

export default function FormRenderer(props: any) {
    const {t} = useTranslation();
    const {handleSubmit, shouldButtonDisable} = props;
    return (
        <form className={"rounded-md mb-4 p-6"} onSubmit={handleSubmit}>
            {props.children}
            <button
                disabled={shouldButtonDisable}
                className="bg-[#007AFF] hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                type="submit"
            >
                {t("SUBMIT")}
            </button>
        </form>
    );
}
