// The product name lives in one file so it changes in one flick.
// This is the lane copy. The root /brand.json replaces it in a follow-up change,
// and only the import path below has to move.
import brandFile from "../brand.json";

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
