/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 10:23
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import HeadingRenderer from '@app/components/ui/HeadingRenderer';

export default function FlexRowContainer(props: any) {
    return (
        <>
            {!!props.title ? <HeadingRenderer>{props.title}</HeadingRenderer> : null}
            <div className={'flex flex-col-reverse lg:flex-row lg:justify-between mt-5'}>{props.children}</div>
        </>
    );
}
