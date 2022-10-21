import HeadingRenderer from "@app/components/ui/HeadingRenderer";
import PaymentCardRenderer from "@app/components/landingpage/PaymentCardRenderer";
import {useTranslation} from "next-i18next";
import LandingPageSectionContainer from "@app/components/landingpage/LandingPageSectionContainer";

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
            <div className="lg:grid lg:grid-cols-3 sm:gap-6 xl:gap-10 lg:space-y-0">
                <PaymentCardRenderer title={"Individual"}
                                     description={"Best for personal user"}
                                     amount={"10 euro"}
                                     features={basicFeatures}
                                     type={plans.INDIVIDUAL}
                                     buttonTitle={"Try 7 days for free"}
                                     plan={"monthly"}/>
                <PaymentCardRenderer title={"Business"}
                                     description={"Best for small and medium-sized businesses."}
                                     amount={"20 euro"}
                                     type={plans.BUSINESS}
                                     plan={"month/user"}
                                     features={proFeatures}
                                     recommended={true}/>
                <PaymentCardRenderer title={"Enterprise"}
                                     description={"Best for large enterprises"}
                                     features={ultroProFeatures}
                                     amount={"$7"}
                                     type={plans.ENTERPRISE}
                                     plan={"yearly"}/>
            </div>
        </LandingPageSectionContainer>
    );
}