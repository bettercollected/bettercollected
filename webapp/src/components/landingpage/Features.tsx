/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 10:33
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import Image from "next/image";
import cardImage from "@app/assets/card.svg";
import FeaturesContainer from "@app/containers/landingpage/FeaturesContainer";
import HeadingRenderer from "@app/components/ui/HeadingRenderer";
import diagram from '@app/assets/Diagram.svg';

export default function Features() {
    return (
        <>
            <HeadingRenderer>Features</HeadingRenderer>
            <div className={"flex justify-center items-center"}>
                <Image src={diagram} width={"700"} height={"700"}/>
            </div>
            <FeaturesContainer>
                <div>
                    <Image
                        alt={"features"}
                        src={cardImage}
                        className={"md:h-auto object-cover md:w-48"}
                        width={"400"}
                        height={"300"}
                    />
                </div>
                <div className="ml-6 mr-6 flex flex-col">
                    <h5 className="text-2xl text-blue-500 font-bold mb-2">CCPA,GDPR compilance</h5>
                    <p className="text-gray-700 text-base mb-4">
                        The most important differences between the GDPR and CCPA is about prior consent versus opting
                        out. The GDPR requires that users give their clear and affirmative consent prior to having their
                        personal data collected and processed, whereas the CCPA requires businesses to make it possible
                        for consumers to opt out of having their data disclosed or sold to third parties.
                    </p>
                </div>
            </FeaturesContainer>

            <FeaturesContainer invert={true}>
                <div>
                    <Image
                        alt={"features"}
                        src={cardImage}
                        className={"md:h-auto object-cover md:w-48"}
                        width={"400"}
                        height={"300"}
                    />
                </div>
                <div className="ml-6 mr-6 flex flex-col">
                    <h5 className="text-2xl text-blue-500 font-bold mb-2">Form Builders</h5>
                    <p className="text-gray-700 text-base mb-4">
                        This is a wider card with supporting text below as a natural lead-in
                        to additional content. This content is a little bit longer.
                    </p>
                </div>
            </FeaturesContainer>

            <FeaturesContainer invert={false}>
                <div>
                    <Image
                        alt={"features"}
                        src={cardImage}
                        className={"md:h-auto object-cover md:w-48"}
                        width={"400"}
                        height={"300"}
                    />
                </div>
                <div className="ml-6 mr-6 flex flex-col">
                    <h5 className="text-2xl text-blue-500 font-bold mb-2">Data analysis</h5>
                    <p className="text-gray-700 text-base mb-4">
                        This is a wider card with supporting text below as a natural lead-in
                        to additional content. This content is a little bit longer.
                    </p>
                </div>
            </FeaturesContainer>
            <FeaturesContainer invert={true}>
                <div>
                    <Image
                        alt={"features"}
                        src={cardImage}
                        className={"md:h-auto object-cover md:w-48"}
                        width={"400"}
                        height={"300"}
                    />
                </div>
                <div className="ml-6 mr-6 flex flex-col">
                    <h5 className="text-2xl text-blue-500 font-bold mb-2">Record form responsee</h5>
                    <p className="text-gray-700 text-base mb-4">
                        This is a wider card with supporting text below as a natural lead-in
                        to additional content. This content is a little bit longer.
                    </p>
                </div>
            </FeaturesContainer>
        </>
    );
}
