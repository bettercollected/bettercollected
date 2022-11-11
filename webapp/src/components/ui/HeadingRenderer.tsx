/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 10:40
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function HeadingRenderer(props: any) {
    return (
        <>
            <h2 className={`text-[#007AFF] text-3xl md:text-4xl font-bold lg:text-6xl text-center mb-4`}>{props.children}</h2>
            {!!props.description ? <p className={'text-gray-500 text-md text-center font-normal lg:text-center mb-4'}>{props.description}</p> : null}
        </>
    );
}
