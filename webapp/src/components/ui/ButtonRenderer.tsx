/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-18
 * Time: 16:01
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function ButtonRenderer(props: any) {
    const onClick = props?.onClick;
    return (
        <button
            className={
                "border-solid border-[1px] focus:ring-4 focus:ring-primary-200 p-3 pl-8 pr-8 text-white rounded-md bg-[#007AFF]"
            }
            onClick={onClick}
        >
            {props.children}
        </button>
    )
}