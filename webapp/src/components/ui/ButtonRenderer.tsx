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
                "border-solid border-[1px] p-3 text-white rounded-md bg-[#006FE8]"
            }
            onClick={onClick}
        >
            {props.children}
        </button>
    )
}