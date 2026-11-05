// Render diagrams/mermaid/*.md to diagrams/images/*.svg with pele.
//
// Run by hand when a source changes, and commit the SVGs. build.py inlines them,
// so publishing needs no node:
//
//   npm install --no-save pele@1.13.0 && node scripts/diagrams.mjs
//
// The SVGs carry no colours of their own. pele writes CSS variables, and build.py
// sets those from the site's tokens, so dark mode comes with the page.
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { render } from "pele";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SRC = join(ROOT, "diagrams", "mermaid");
const OUT = join(ROOT, "diagrams", "images");

// Class is owl:Class, so it has no page here to link to.
const NO_PAGE = new Set(["Class"]);

// Every other node id is the term's local name, so each box can link to its page.
const withLinks = (text) => {
  const ids = [...text.matchAll(/^\s+(\w+)\["/gm)].map((m) => m[1]);
  const clicks = ids.filter((id) => !NO_PAGE.has(id)).map((id) => `    click ${id} href "/${id}"`);
  return `${text}\n${clicks.join("\n")}\n`;
};

// pele captions a box inside its top edge, where the arrows leaving the box cross
// the text. Nothing runs below a box, so the caption goes there.
const captionsBelow = (svg) =>
  svg.replace(
    /(<rect x="([\d.]+)" y="([\d.]+)" width="[\d.]+" height="([\d.]+)"[^>]*\/><text class="pele-cluster-label"[^>]*?) x="[\d.]+" y="[\d.]+" text-anchor="middle"/g,
    (_, head, x, y, h) => `${head} x="${x}" y="${Number(y) + Number(h) + 17}" text-anchor="start"`,
  );

mkdirSync(OUT, { recursive: true });
for (const file of readdirSync(SRC).filter((f) => f.endsWith(".md"))) {
  const fence = readFileSync(join(SRC, file), "utf8").match(/```mermaid\n([\s\S]*?)```/);
  if (!fence) throw new Error(`${file}: no mermaid block`);
  const { svg, links } = render(withLinks(fence[1]), {
    fontFamily: '"Archivo", sans-serif',
    fontSize: 15,
    padding: 28, // room for a caption under the lowest box
  });
  writeFileSync(join(OUT, `${basename(file, ".md")}.svg`), `${captionsBelow(svg)}\n`);
  console.log(file, `${links.length} links`);
}
