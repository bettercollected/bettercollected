/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-20
 * Time: 07:26
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function FeaturesContainer(props:any) {
    // const inverted = props?.invert;
    return(
        <>
            <div
                className={`flex items-center gap-4 mb-2 p-4 border-[1px] rounded-md border-solid border-[#ced1fa]`}
            >
                {props.children}
            </div>
        </>
    )
}