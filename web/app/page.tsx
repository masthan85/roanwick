import { Cancellation, Continuity, FactStrip, FinalCta, ForProfessionals, Hero, HowItWorks, Questions, Services, Verification } from "@/components/home/sections";

export default function Home() {
  return (
    <>
      <Hero />
      <FactStrip />
      <Cancellation />
      <Continuity />
      <Verification />
      <HowItWorks />
      <Services />
      <Questions />
      <ForProfessionals />
      <FinalCta />
    </>
  );
}
