import { cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const sourceDir = path.join(root, "docs");
const outputDir = path.join(root, "_site");
const dataDir = path.join(root, "data");
const backgroundFile = path.join(root, "background.md");

await rm(outputDir, { recursive: true, force: true });
await cp(sourceDir, outputDir, {
  recursive: true,
  filter(source) {
    const relative = path.relative(sourceDir, source);
    return relative !== path.join("assets", "site-data.js");
  },
});

const siteData = {
  background: await readOptionalText(backgroundFile),
  categories: [],
};
const categoryNames = categoryNamesFromBackground(siteData.background);

for (const categoryEntry of await sortedDirectories(dataDir)) {
  const categorySlug = categoryEntry.name;
  const categoryPath = path.join(dataDir, categorySlug);
  const category = {
    slug: categorySlug,
    name: categoryNames.get(categorySlug) ?? titleFromSlug(categorySlug),
    pairs: [],
  };

  for (const pairEntry of await sortedDirectories(categoryPath)) {
    const pairPath = path.join(categoryPath, pairEntry.name);
    const pair = {
      id: pairEntry.name,
      files: [],
    };

    const files = await readdir(pairPath, { withFileTypes: true });
    const jsonFiles = files
      .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
      .sort((left, right) => fileSortKey(left.name).localeCompare(fileSortKey(right.name)));

    for (const fileEntry of jsonFiles) {
      const filePath = path.join(pairPath, fileEntry.name);
      const payload = JSON.parse(await readFile(filePath, "utf8"));
      pair.files.push({
        stem: path.basename(fileEntry.name, ".json"),
        filename: fileEntry.name,
        condition: payload.condition ?? "",
        turns: payload.turns ?? [],
        metadata: payload.metadata ?? {},
      });
    }

    category.pairs.push(pair);
  }

  siteData.categories.push(category);
}

validateSiteData(siteData);

await mkdir(path.join(outputDir, "assets"), { recursive: true });
await writeFile(
  path.join(outputDir, "assets", "site-data.js"),
  `window.THERAPEUTIC_SITE_DATA = ${JSON.stringify(siteData, null, 2)};\n`,
  "utf8",
);
await writeFile(path.join(outputDir, ".nojekyll"), "", "utf8");

console.log(
  `Built ${outputDir} with ${siteData.categories.length} categories and ${countFiles(siteData)} JSON records.`,
);

async function sortedDirectories(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory())
    .sort((left, right) => naturalCompare(left.name, right.name));
}

async function readOptionalText(filePath) {
  try {
    return await readFile(filePath, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") {
      return "";
    }
    throw error;
  }
}

function titleFromSlug(slug) {
  const smallWords = new Set(["and", "of", "the", "to", "in"]);
  return slug
    .split("-")
    .filter(Boolean)
    .map((word, index) => {
      if (index > 0 && smallWords.has(word)) {
        return word;
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
}

function categoryNamesFromBackground(markdown) {
  const names = new Map();
  const headingPattern = /^##\s+\**(.+?)\**\s*$/gm;
  let match;
  while ((match = headingPattern.exec(markdown)) !== null) {
    const name = match[1].replace(/\*\*/g, "").trim();
    names.set(slugFromTitle(name), name);
  }
  return names;
}

function slugFromTitle(title) {
  return title
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function fileSortKey(filename) {
  const stem = path.basename(filename, ".json");
  const side = stem.startsWith("a") ? "0" : stem.startsWith("b") ? "1" : "2";
  const base = stem === "a" || stem === "b" ? "0" : "1";
  return `${side}:${base}:${stem}`;
}

function naturalCompare(left, right) {
  return left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" });
}

function validateSiteData(data) {
  if (!data.categories.length) {
    throw new Error("No data categories found.");
  }

  const errors = [];
  for (const category of data.categories) {
    if (!category.pairs.length) {
      errors.push(`${category.slug}: no pair directories found`);
    }

    for (const pair of category.pairs) {
      if (!pair.files.length) {
        errors.push(`${category.slug}/${pair.id}: no JSON files found`);
      }

      for (const file of pair.files) {
        if (!file.condition) {
          errors.push(`${category.slug}/${pair.id}/${file.filename}: missing condition`);
        }
        if (!Array.isArray(file.turns) || file.turns.length === 0) {
          errors.push(`${category.slug}/${pair.id}/${file.filename}: missing turns`);
        }
        if (!Array.isArray(file.metadata?.reasons) || file.metadata.reasons.length === 0) {
          errors.push(`${category.slug}/${pair.id}/${file.filename}: missing metadata.reasons`);
        }
      }
    }
  }

  if (errors.length) {
    throw new Error(`Invalid site data:\n${errors.join("\n")}`);
  }
}

function countFiles(data) {
  return data.categories.reduce(
    (categoryTotal, category) =>
      categoryTotal + category.pairs.reduce((pairTotal, pair) => pairTotal + pair.files.length, 0),
    0,
  );
}
