/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 16:07
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function FormInput(props: any) {
  const { label, placeholder, id, handleChange } = props;

  return (
    <div className={"flex flex-col mb-4"}>
      <label
        className={"block text-gray-700 text-sm font-normal mb-2"}
        htmlFor={id}
      >
        {label}
      </label>
      <input
        className="border text-gray-900 text-sm rounded-lg w-full p-2.5"
        id={"email"}
        type="text"
        placeholder={placeholder}
        onChange={(e) => handleChange(id, e.target.value)}
      />
    </div>
  );
}
