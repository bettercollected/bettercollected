/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 10:33
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import LandingPageContainer from "@app/containers/landingpage/LandingPageContainer";
import Image from "next/image";
import cardImage from "@app/assets/card.svg";
import FeaturesContainer from "@app/containers/landingpage/FeaturesContainer";
import HeadingRenderer from "@app/components/ui/HeadingRenderer";

export default function Features() {
  return (
    <>
      <HeadingRenderer>Features</HeadingRenderer>
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
          <h5 className="text-2xl text-blue-500 font-bold mb-2">Card title</h5>
          <p className="text-gray-700 text-base mb-4">
            This is a wider card with supporting text below as a natural lead-in
            to additional content. This content is a little bit longer.
          </p>
          <p className="text-gray-600 text-xs">Last updated 3 mins ago</p>
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
          <h5 className="text-2xl text-blue-500 font-bold mb-2">Card title</h5>
          <p className="text-gray-700 text-base mb-4">
            This is a wider card with supporting text below as a natural lead-in
            to additional content. This content is a little bit longer.
          </p>
          <p className="text-gray-600 text-xs">Last updated 3 mins ago</p>
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
          <h5 className="text-2xl text-blue-500 font-bold mb-2">Card title</h5>
          <p className="text-gray-700 text-base mb-4">
            This is a wider card with supporting text below as a natural lead-in
            to additional content. This content is a little bit longer.
          </p>
          <p className="text-gray-600 text-xs">Last updated 3 mins ago</p>
        </div>
      </FeaturesContainer>
    </>
  );
}
