/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 10:33
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import Diagram from '@app/assets/svgs/Diagram.svg';
import brand from '@app/assets/svgs/brand.svg';
import cardImage from '@app/assets/svgs/card.svg';
import gdpr from '@app/assets/svgs/gdpr.svg';
import portal from '@app/assets/svgs/portal.svg';
import privacy from '@app/assets/svgs/privacy.svg';
import FeaturesContainer from '@app/components/landingpage/FeaturesContainer';
import LandingPageSectionContainer from '@app/components/landingpage/LandingPageSectionContainer';
import HeadingRenderer from '@app/components/ui/HeadingRenderer';

export default function Features() {
    const { t } = useTranslation();

    function CardContent(props: any) {
        const { imageSrc, title, description } = props;
        return (
            <div className="flex flex-col sm:flex-row">
                <div>
                    <Image alt={title} src={imageSrc} className={'w-[100%]'} />
                </div>
                <div className={'flex flex-col'}>
                    <h2 className={'font-semibold text-2xl'}>{title}</h2>
                    <p className={'text-gray-500'}>{description}</p>
                </div>
            </div>
        );
    }

    return (
        <LandingPageSectionContainer sectionId={'features'}>
            {/*<div className={" lg:w-[1350px] p-8 lg:m-auto flex flex-col"} id={"features"}>*/}
            <HeadingRenderer>{t('FEATURES')}</HeadingRenderer>
            <div className={'flex justify-center items-center mt-10 mb-12'}>
                <Image src={Diagram} width={1000} />
            </div>

            <div className={'grid grid-rows-1 lg:grid-rows-2 lg:grid-flow-col lg:gap-6 '}>
                <FeaturesContainer>
                    <CardContent title={t('FEATURE_1')} description={t('FEATURE_1_DESC')} imageSrc={privacy} />
                </FeaturesContainer>

                <FeaturesContainer>
                    <CardContent title={t('FEATURE_2')} description={t('FEATURE_2_DESC')} imageSrc={portal} />
                </FeaturesContainer>

                <FeaturesContainer>
                    <CardContent title={t('FEATURE_3')} description={t('FEATURE_3_DESC')} imageSrc={brand} />
                </FeaturesContainer>

                <FeaturesContainer>
                    <CardContent title={t('FEATURE_4')} description={t('FEATURE_4_DESC')} imageSrc={gdpr} />
                </FeaturesContainer>
            </div>
            {/*</div>*/}
        </LandingPageSectionContainer>
    );
}
