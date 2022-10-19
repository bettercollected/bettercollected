import HeadingRenderer from "@app/components/ui/HeadingRenderer";
import PaymentCardRenderer from "@app/components/landingpage/PaymentCardRenderer";
import {useTranslation} from "next-i18next";
import LandingPageSectionContainer from "@app/components/landingpage/LandingPageSectionContainer";

const basicFeatures = ["Individual configuration","No setup, or hidden fees","Team size: 1 developer", "Basic support: 6 months","Free updates: 6 months"];
const proFeatures = ["Individual configuration","No setup, or hidden fees","Team size: 3 developer", "Basic support: 12 months","Free updates: Forever"];
const ultroProFeatures = ["Individual configuration","No setup, or hidden fees","Team size: 5 developer", "Basic support: Forever","Free updates: Forever   "];

export default function Payment() {
    return (
        <LandingPageSectionContainer sectionId={"payment"}>
            <HeadingRenderer
                description={"Here at Flowbite we focus on markets where technology, innovation, and capital can unlock long-term value and drive economic growth."}>
                Ready to get started?
            </HeadingRenderer>
            <div className="space-y-8 lg:grid lg:grid-cols-3 sm:gap-6 xl:gap-10 lg:space-y-0">
                <PaymentCardRenderer title={"Starter"}
                                     description={"Best option for personal use only"}
                                     amount={"$9"}
                                     features={basicFeatures}
                                     buttonTitle={"Try 7 days for free"}
                                     plan={"monthly"}/>
                <PaymentCardRenderer title={"Pro"}
                                     description={"Best option for personal use & for your next project."}
                                     amount={"$5"}
                                     plan={"monthly"}
                                     features={proFeatures}
                                     recommended={true}/>
                <PaymentCardRenderer title={"Ultro Pro Max"}
                                     description={"Best option for a professional"}
                                     features={ultroProFeatures}
                                     amount={"$7"}
                                     plan={"yearly"}/>
            </div>
        </LandingPageSectionContainer>
    );
}