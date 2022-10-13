import type { NextPage } from "next";
import Navbar from "@app/components/landingpage/Navbar";
import { serverSideTranslations } from "next-i18next/serverSideTranslations";
import Banner from "@app/components/landingpage/Banner";

const Home: NextPage = () => {
  return (
    <>
      <div>
        <Navbar />
        <Banner />
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
