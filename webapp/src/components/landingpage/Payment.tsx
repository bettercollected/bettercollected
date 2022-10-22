import HeadingRenderer from "@app/components/ui/HeadingRenderer";
import PaymentCardRenderer from "@app/components/landingpage/PaymentCardRenderer";
import {useTranslation} from "next-i18next";
import LandingPageSectionContainer from "@app/components/landingpage/LandingPageSectionContainer";
import environments from "@app/configs/environments";
import Advertising from "@app/components/landingpage/Advertising";

const basicFeatures = ["Unlimited forms and responses","Custom domain","Custom form URLs", "Single user","Single workspace"];
const proFeatures = ["Unlimited forms and responses","Custom domain","Custom form URLs", "Unlimited workspaces","Unlimited users"];
const ultroProFeatures = ["Everything in Business","Single Sign On","Premium support"];

enum plans {
    INDIVIDUAL,BUSINESS,ENTERPRISE
}

export default function Payment() {
    const {t} = useTranslation();
    return (
        <LandingPageSectionContainer sectionId={"payment"}>
            <HeadingRenderer
                description={t("PAYMENT_DESC")}>
                {t("READY_TO_GET_STARTED")}
            </HeadingRenderer>
            <div className="lg:grid lg:grid-cols-3 sm:gap-6 xl:gap-10 lg:space-y-0 mb-8">
                <PaymentCardRenderer title={t("INDIVIDUAL")}
                                     description={t("INDIVIDUAL_1")}
                                     amount={"10 euro"}
                                     features={basicFeatures}
                                     formUrl={"/pricing/individual-plan"}
                                     type={plans.INDIVIDUAL}
                                     buttonTitle={"Try 7 days for free"}
                                     plan={t("INDIVIDUAL_2")}/>
                <PaymentCardRenderer title={"Business"}
                                     description={"Best for small and medium-sized businesses."}
                                     formUrl={"/pricing/business-plan"}
                                     amount={"20 euro"}
                                     type={plans.BUSINESS}
                                     plan={`${t("INDIVIDUAL")}`}
                                     features={proFeatures}
                                     recommended={true}/>
                <PaymentCardRenderer title={"Enterprise"}
                                     description={"Best for large enterprises"}
                                     formUrl={"/pricing/enterprise-plan"}
                                     features={ultroProFeatures}
                                     amount={""}
                                     type={plans.ENTERPRISE}
                                     plan={""}/>
            </div>
            <Advertising/>
        </LandingPageSectionContainer>
    );
}