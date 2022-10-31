import HeadingRenderer from '@app/components/ui/HeadingRenderer';

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 10:46
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function FeaturesContainer(props: any) {
    const inverted = props?.invert;
    return (
        <>
            <div className={`flex ${inverted ? 'flex-row-reverse' : 'flex-row'} justify-between mb-24 p-8 justify-between`}>{props.children}</div>
        </>
    );
}
