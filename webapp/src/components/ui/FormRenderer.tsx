/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 16:01
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import {useTranslation} from "next-i18next";
import ButtonRenderer from "@app/components/ui/ButtonRenderer";

export default function FormRenderer(props: any) {
    const {t} = useTranslation();
    const {handleSubmit, shouldButtonDisable} = props;
    return (
        <form className={"rounded-md mb-4 p-6"} onSubmit={handleSubmit}>
            {props.children}
            <ButtonRenderer disabled={shouldButtonDisable}>{t('SUBMIT')}</ButtonRenderer>
        </form>
    );
}
