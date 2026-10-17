// Generates src/generated/form-spec.ts from the committed form spec JSON
// Schema (docs/spec). Property titles are pydantic's field names; they are
// dropped first so that every field is typed inline instead of as a
// one-off alias. Run with `npm run generate` (which also regenerates the
// OpenAPI types).
import { readFile, writeFile } from "node:fs/promises";
import { compile } from "json-schema-to-typescript";

const SOURCE = new URL("../../../docs/spec/form-spec-v1.schema.json", import.meta.url);
const TARGET = new URL("../src/generated/form-spec.ts", import.meta.url);

function dropPropertyTitles(node) {
  if (Array.isArray(node)) return node.forEach(dropPropertyTitles);
  if (!node || typeof node !== "object") return;
  for (const [key, value] of Object.entries(node)) {
    if (key === "properties" && value && typeof value === "object") {
      for (const property of Object.values(value)) {
        if (property && typeof property === "object") delete property.title;
        dropPropertyTitles(property);
      }
    } else if (key === "anyOf" || key === "oneOf" || key === "allOf" || key === "items") {
      for (const member of [value].flat()) {
        if (member && typeof member === "object" && !member.$ref) delete member.title;
      }
      dropPropertyTitles(value);
    } else {
      dropPropertyTitles(value);
    }
  }
}

const schema = JSON.parse(await readFile(SOURCE, "utf8"));
dropPropertyTitles(schema);
schema.title = "FormSpec";

const output = await compile(schema, "FormSpec", {
  additionalProperties: false,
  unreachableDefinitions: true,
  bannerComment:
    "/* Generated from docs/spec/form-spec-v1.schema.json by scripts/generate.mjs. Do not edit. */",
  style: { singleQuote: false },
});
await writeFile(TARGET, output);
console.log("Wrote src/generated/form-spec.ts");
