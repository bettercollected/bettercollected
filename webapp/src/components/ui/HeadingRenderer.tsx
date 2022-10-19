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
      <div
        className={`text-[#007AFF] text-4xl font-bold text-center ${
          !!props.description ? "mb-1" : "mb-1"
        }`}
      >
        {props.children}
      </div>
      {!!props.description ? (
        <div className={"text-gray-500 font-semibold text-center mb-20"}>
          {props.description}
        </div>
      ) : null}
    </>
  );
}
