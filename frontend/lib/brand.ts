// The product name lives in one file at the repo root, so it changes in one flick.
// Nothing else under /frontend spells it out; check:brand fails the build if it does.
import brandFile from "../../brand.json";

export type Brand = {
  name: string;
  short_name: string;
  tagline: string;
};

export const brand: Brand = {
  name: brandFile.name,
  short_name: brandFile.short_name,
  tagline: brandFile.tagline,
};
