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
            disabled={!!props.disabled}
            className={
                "p-4 pt-2 pb-2 text-white rounded-md bg-[#007AFF]"
            }
            onClick={onClick}
        >
            <span className={"z-2"}>{props.children}</span>
        </button>
    );
}