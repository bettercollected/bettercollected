/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 10:33
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import Image from "next/image";
import cardImage from "@app/assets/card.svg";
import HeadingRenderer from "@app/components/ui/HeadingRenderer";
import diagram from '@app/assets/Diagram3.svg';
import privacy from '@app/assets/privacy.svg';
import data from '@app/assets/Group.svg';
import form from '@app/assets/form.svg';
import Vector from '@app/assets/Vector.svg';

import FeaturesContainer from "@app/components/landingpage/FeaturesContainer";
import LandingPageSectionContainer from "@app/components/landingpage/LandingPageSectionContainer";
import {useTranslation} from "next-i18next";

export default function Features() {

    const {t} = useTranslation();

    function CardContent(props: any) {
        const {imageSrc, title, description} = props;
        return (
            <>
                <div>
                    <Image
                        alt={title}
                        src={imageSrc}
                        className={"w-[100%]"}
                    />
                </div>
                <div className={"flex flex-col"}>
                    <h2 className={"font-semibold text-2xl"}>{title}</h2>
                    <p className={"text-gray-500"}>{description}</p>
                </div>
            </>
        )
    }


    return (
        <LandingPageSectionContainer sectionId={"features"}>
            {/*<div className={" lg:w-[1350px] p-8 lg:m-auto flex flex-col"} id={"features"}>*/}
                <HeadingRenderer>{t("FEATURES")}</HeadingRenderer>
                <div className={"flex justify-center items-center"}>
                    <Image src={diagram} width={"700"} height={"700"}/>
                </div>

                <div className={"grid grid-rows-1 lg:grid-rows-2 lg:grid-flow-col lg:gap-6 "}>

                    <FeaturesContainer>
                        <CardContent
                            title={t("FEATURE_1")}
                            description={t("FEATURE_1_DESC")}
                            imageSrc={privacy}/>
                    </FeaturesContainer>


                    <FeaturesContainer>
                        <CardContent
                            title={t("FEATURE_2")}
                            description={t("FEATURE_2_DESC")}
                            imageSrc={form}
                        />
                    </FeaturesContainer>

                    <FeaturesContainer>
                        <CardContent
                            title={t("FEATURE_3")}
                            description={t("FEATURE_3_DESC")}
                            imageSrc={Vector}
                        />
                    </FeaturesContainer>

                    <FeaturesContainer>
                        <CardContent
                            title={t("FEATURE_4")}
                            description={t("FEATURE_4_DESC")}
                            imageSrc={data}
                        />
                    </FeaturesContainer>
                </div>
            {/*</div>*/}
        </LandingPageSectionContainer>
    );
}
