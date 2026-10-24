- Logic on multiple choice and dropdown questions works. Visibility rules and page jumps that test
  which option a respondent chose never matched: answers hold the chosen option's id, while the
  logic editor, the AI assistant and the seeded "Support triage" template name the option by its
  text. So such questions stayed hidden (or shown), jumps never fired, a jump never chose its
  ending, and the flow view counted every response on the linear path. Conditions now match the
  chosen option by its text or its id (exactly, as before), in the respondent's browser and in the
  server's checks alike; several answers are tested for membership the same way, and text typed as
  "Other" is compared as it is (an "Other" answer is no longer empty). Existing rules work without
  changes. Affected every release since conditional logic shipped in 2.3.0.
