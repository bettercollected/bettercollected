import type { NextPage } from "next";
import Navbar from "@app/components/landingpage/Navbar";
import { serverSideTranslations } from "next-i18next/serverSideTranslations";
import Banner from "@app/components/landingpage/Banner";
import Features from "@app/components/landingpage/Features";
import WaitlistForm from "@app/components/landingpage/WaitlistForm";
import ContactUs from "@app/components/landingpage/ContactUs";

const Home: NextPage = () => {
  return (
    <>
      <Navbar />
      <div className={"min-h-screen box-border p-48 pb-0 pt-5"}>
        <Banner />
      </div>
      <div className={"p-48 pt-5 mb-40"}>
        <WaitlistForm />
        <Features />
        <ContactUs />
      </div>
    </>
  );
};

export default Home;

export async function getServerSideProps({ locale }: any) {
  return {
    props: {
      ...(await serverSideTranslations(locale, ["common"], null, ["en", "de"])),
    },
  };
}
