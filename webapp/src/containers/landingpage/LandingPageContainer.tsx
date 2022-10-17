/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 10:23
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import HeadingRenderer from "@app/components/ui/HeadingRenderer";

export default function LandingPageContainer(props: any) {
  return (
    <div className={"mb-24"}>
      {!!props.title ? <HeadingRenderer>{props.title}</HeadingRenderer> : null}
      <div className={"flex justify-between"}>{props.children}</div>
    </div>
  );
}
